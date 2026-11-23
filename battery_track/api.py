"""
Public APIs for the dealer system (create_order) and the warehouse scanner (scan_pack).

URL pattern:  POST /api/method/battery_track.api.<function_name>
Auth header:  Authorization: token <api_key>:<api_secret>
"""

import json

import frappe
from frappe import _
from frappe.auth import validate_ip_address
from frappe.rate_limiter import rate_limit
from frappe.twofactor import should_run_2fa
from frappe.utils import add_days, cint, flt, now_datetime, nowdate

from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

from battery_track.setup.test_data import COMPANY, FINISHED_GOODS


# ---------------------------------------------------------------------------
# 0. App login (username + password -> API key/secret)
# ---------------------------------------------------------------------------
@frappe.whitelist(allow_guest=True, methods=["POST"])  # guest: the user is not logged in yet
@rate_limit(limit=5, seconds=60)  # max 5 tries per minute per IP: slows down password guessing
def app_login(usr, pwd):
	"""Scanner app login. Checks the password, then returns the user's API key + secret.

	The app then uses token auth for every call, the same as before.
	Why not a normal session cookie? Cookies across sites (web app) and on mobile need extra
	handling (SameSite, CSRF token). A token works the same everywhere.
	"""
	# Frappe's own password check: also counts failed attempts and locks the user after too many.
	# On a wrong password it writes an Authentication Log and raises AuthenticationError (HTTP 401).
	login_manager = frappe.local.login_manager
	login_manager.authenticate(usr, pwd)
	user = login_manager.user

	# Safety rules before we hand out a long-lived key
	if user == "Administrator":
		frappe.throw(_("Administrator cannot use the scanner app. Use a warehouse user."), frappe.PermissionError)
	if should_run_2fa(user):
		# this endpoint would skip the OTP step, so 2FA users must not log in here
		frappe.throw(_("Two-factor login is on for this user. Ask admin for API keys instead."), frappe.PermissionError)
	if "Stock User" not in frappe.get_roles(user):
		frappe.throw(_("User {0} needs the Stock User role to scan").format(user), frappe.PermissionError)
	validate_ip_address(user)  # respects "Restrict IP" on the User, if set

	user_doc = frappe.get_doc("User", user)
	api_secret = user_doc.get_password("api_secret", raise_exception=False)  # stored encrypted

	# first login from the app: create key + secret (later logins reuse them, so other devices keep working)
	if not user_doc.api_key or not api_secret:
		user_doc.api_key = user_doc.api_key or frappe.generate_hash(length=15)
		api_secret = frappe.generate_hash(length=15)
		user_doc.api_secret = api_secret
		user_doc.save(ignore_permissions=True)  # guest request: the user can't have "write" on User yet

	return {"api_key": user_doc.api_key, "api_secret": api_secret, "full_name": user_doc.full_name}


# ---------------------------------------------------------------------------
# 1. Order API (idempotent)
# ---------------------------------------------------------------------------
@frappe.whitelist(methods=["POST"])  # POST only: this API creates data
def create_order(external_order_id, customer, items, delivery_date=None):
	"""Create a Sales Order from the dealer's system.

	items: list (or JSON string) like [{"item_code": "PACK-48V", "qty": 1, "rate": 12000}]
	If the same external_order_id comes again, return the existing order (no duplicate).
	"""
	# Permission check: whitelisted = reachable by any logged-in user, so we must check rights ourselves
	frappe.has_permission("Sales Order", "create", throw=True)

	# Idempotency: the dealer may retry after a timeout. Same ID => same Sales Order.
	existing = frappe.db.get_value(
		"Sales Order", {"external_order_id": external_order_id}, ["name", "docstatus"], as_dict=True
	)
	if existing:
		return {
			"ok": True,
			"created": False,
			"sales_order": existing.name,
			"message": _("Order {0} already exists as {1}").format(external_order_id, existing.name),
		}

	# items comes as a JSON string when sent as form data, as a list when sent as JSON body
	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		frappe.throw(_("items cannot be empty"))

	if not frappe.db.exists("Customer", customer):
		frappe.throw(_("Customer {0} not found").format(customer))

	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"company": COMPANY,
			"customer": customer,
			"external_order_id": external_order_id,
			"transaction_date": nowdate(),
			"delivery_date": delivery_date or add_days(nowdate(), 7),
			"set_warehouse": FINISHED_GOODS,  # packs are shipped from Finished Goods
			"items": [
				{
					"item_code": row["item_code"],
					"qty": row["qty"],
					"rate": row.get("rate"),  # if not given, ERPNext takes it from the price list
				}
				for row in items
			],
		}
	)
	so.insert()
	so.submit()  # a submitted order is a confirmed order, ready for picking

	return {
		"ok": True,
		"created": True,
		"sales_order": so.name,
		"message": _("Sales Order {0} created").format(so.name),
	}


# ---------------------------------------------------------------------------
# 2. Scan API
# ---------------------------------------------------------------------------
@frappe.whitelist(methods=["POST"])
def scan_pack(sales_order, serial_no):
	"""Warehouse person scans a pack serial while picking for a Sales Order.

	Always returns {"ok": true/false, "message": "..."} and always saves a Scan Log.
	We RETURN errors instead of frappe.throw, because a throw would roll back the
	transaction and the error Scan Log would be lost.
	"""
	# Permission: user must be allowed to create scan logs (Stock User role)
	frappe.has_permission("Scan Log", "create", throw=True)

	serial_no = (serial_no or "").strip()  # barcode scanners often add spaces / newlines

	if not frappe.db.exists("Sales Order", sales_order):
		message = _("Sales Order {0} not found").format(sales_order)
		log_scan(None, serial_no, None, False, message)
		return {"ok": False, "message": message}

	# ...and must be allowed to see this particular order
	frappe.has_permission("Sales Order", "read", doc=sales_order, throw=True)

	# Lock the Sales Order row until this request ends. If two scanners scan for the
	# same order at the same moment, the second waits, so over-scan cannot slip through.
	frappe.db.get_value("Sales Order", sales_order, "name", for_update=True)

	ok, message, item_code = validate_scan(sales_order, serial_no)
	log_scan(sales_order, serial_no, item_code, ok, message)

	return {"ok": ok, "message": message}


def validate_scan(sales_order, serial_no):
	"""Run all checks in order. Returns (ok, message, item_code)."""
	so = frappe.db.get_value("Sales Order", sales_order, ["docstatus", "status"], as_dict=True)
	if so.docstatus != 1 or so.status in ("Closed", "Completed", "On Hold"):
		return False, _("Sales Order {0} is not open for picking (status: {1})").format(sales_order, so.status), None

	# 1. serial exists
	serial = frappe.db.get_value("Serial No", serial_no, ["item_code", "status", "warehouse"], as_dict=True)
	if not serial:
		return False, _("Serial No {0} does not exist").format(serial_no), None

	item_code = serial.item_code

	# 2. its item is in the Sales Order
	ordered_qty = get_ordered_qty(sales_order, item_code)
	if not ordered_qty:
		return False, _("Item {0} is not in Sales Order {1}").format(item_code, sales_order), item_code

	# 3. in stock
	if serial.status != "Active" or not serial.warehouse:
		return False, _("Serial No {0} is not in stock (status: {1})").format(serial_no, serial.status), item_code

	# 4. not already scanned (for this order or another one)
	already = frappe.db.get_value(
		"Scan Log", {"serial_no": serial_no, "result": "Success"}, "sales_order"
	)
	if already == sales_order:
		return False, _("Serial No {0} is already scanned for this order").format(serial_no), item_code
	if already:
		return False, _("Serial No {0} is already scanned for Sales Order {1}").format(serial_no, already), item_code

	# 5. do not scan more than ordered
	scanned_qty = frappe.db.count(
		"Scan Log", {"sales_order": sales_order, "item_code": item_code, "result": "Success"}
	)
	if scanned_qty >= ordered_qty:
		return False, _("All {0} x {1} already scanned for this order").format(int(ordered_qty), item_code), item_code

	return True, _("{0} OK ({1}/{2} scanned for {3})").format(
		serial_no, scanned_qty + 1, int(ordered_qty), item_code
	), item_code


@frappe.whitelist()  # GET is fine: this only reads data
def get_scan_progress(sales_order):
	"""How many of each item are ordered vs scanned, for the scanner app's progress bar.

	Returns {"items": [{"item_code", "item_name", "ordered", "scanned"}], "complete": bool}
	"""
	frappe.has_permission("Sales Order", "read", doc=sales_order, throw=True)

	# ordered qty per item (an item can be on more than one row, so add them up)
	ordered = {}
	names = {}
	for row in frappe.get_all(
		"Sales Order Item",
		filters={"parent": sales_order},
		fields=["item_code", "item_name", "stock_qty"],
		order_by="idx asc",
	):
		ordered[row.item_code] = ordered.get(row.item_code, 0) + row.stock_qty
		names[row.item_code] = row.item_name

	# successful scans per item for this order
	scanned = {}
	for item_code in frappe.get_all(
		"Scan Log", filters={"sales_order": sales_order, "result": "Success"}, pluck="item_code"
	):
		scanned[item_code] = scanned.get(item_code, 0) + 1

	items = [
		{
			"item_code": code,
			"item_name": names[code],
			"ordered": int(qty),
			"scanned": scanned.get(code, 0),
		}
		for code, qty in ordered.items()
	]
	return {"items": items, "complete": all(i["scanned"] >= i["ordered"] for i in items)}


def get_ordered_qty(sales_order, item_code):
	"""Total qty of this item in the Sales Order (the item can be on more than one row)."""
	rows = frappe.get_all(
		"Sales Order Item", filters={"parent": sales_order, "item_code": item_code}, pluck="stock_qty"
	)
	return sum(rows)


def log_scan(sales_order, serial_no, item_code, ok, message):
	"""Save every scan (success or error) as an audit trail."""
	frappe.get_doc(
		{
			"doctype": "Scan Log",
			"sales_order": sales_order,  # None when the scanned order does not exist
			"serial_no": serial_no,
			"item_code": item_code,
			"result": "Success" if ok else "Error",
			"message": message,
			"scanned_by": frappe.session.user,
			"scanned_at": now_datetime(),
		}
	).insert()


# ---------------------------------------------------------------------------
# 4. Build N packs from a Work Order (one click, one Manufacture entry PER pack)
# ---------------------------------------------------------------------------
MAX_PACKS_PER_CLICK = 20  # keeps one request short; bigger runs = click again


@frappe.whitelist(methods=["POST"])
def build_packs(work_order, count):
	"""Build `count` packs: makes `count` separate Manufacture entries (qty 1 each).

	Why not one entry with qty 10? Then we can't know which 16 cells went into which pack.
	All-or-nothing: if pack 7 fails, the whole request rolls back and no pack is built.
	"""
	count = cint(count)
	frappe.has_permission("Stock Entry", "submit", throw=True)
	wo = frappe.get_doc("Work Order", work_order)
	wo.check_permission("read")

	if wo.docstatus != 1:
		frappe.throw(_("Submit the Work Order first"))
	if wo.status in ("Stopped", "Closed"):
		frappe.throw(_("Work Order {0} is {1}").format(wo.name, wo.status))

	remaining = cint(flt(wo.qty) - flt(wo.produced_qty))
	if count < 1 or count > MAX_PACKS_PER_CLICK:
		frappe.throw(_("Build between 1 and {0} packs per click").format(MAX_PACKS_PER_CLICK))
	if count > remaining:
		frappe.throw(_("Only {0} packs are left to build on {1}").format(remaining, wo.name))

	check_stock_for_packs(wo, count)  # clear error BEFORE we start, instead of failing at pack 7

	packs = []
	for _i in range(count):
		# ERPNext's own "Finish" logic: fills raw materials + finished pack for qty 1
		se = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", qty=1))
		pick_raw_material_serials(se)
		se.insert()
		se.submit()  # our on_submit hook (events/stock_entry.py) creates Pack Traceability
		pack = frappe.db.get_value("Pack Traceability", {"stock_entry": se.name}, "name")
		packs.append(pack or se.name)

	return {
		"ok": True,
		"packs": packs,
		"message": _("{0} packs built: {1}").format(len(packs), ", ".join(packs)),
	}


def check_stock_for_packs(wo, count):
	"""Is there enough raw material for `count` packs? Tell the user exactly what is short."""
	short = []
	for row in wo.required_items:
		per_pack = flt(row.required_qty) / flt(wo.qty)  # e.g. 16 cells per pack
		needed = per_pack * count
		warehouse = row.source_warehouse or wo.source_warehouse

		if frappe.get_cached_value("Item", row.item_code, "has_serial_no"):
			# serialised: count the serials that are really on the shelf
			available = frappe.db.count(
				"Serial No", {"item_code": row.item_code, "warehouse": warehouse, "status": "Active"}
			)
		else:
			available = flt(frappe.db.get_value("Bin", {"item_code": row.item_code, "warehouse": warehouse}, "actual_qty"))

		if available < needed:
			short.append(_("{0}: need {1:g}, have {2:g}").format(row.item_code, needed, flt(available)))

	if short:
		frappe.throw(_("Not enough stock for {0} packs.<br>{1}").format(count, "<br>".join(short)))


def pick_raw_material_serials(se):
	"""Fill serials on raw material rows, oldest first (FIFO), so we control exactly which cells go in.

	Each entry is submitted before the next one is made, so used serials are no longer
	"Active" and the next pack automatically gets the next 16 cells.
	The finished pack row stays empty: ERPNext creates PACK-#### from the item's series on submit.
	"""
	for row in se.items:
		if not row.s_warehouse or row.serial_no:
			continue  # finished good, or serials already filled
		if not frappe.get_cached_value("Item", row.item_code, "has_serial_no"):
			continue  # e.g. casing: no serial

		row.use_serial_batch_fields = 1  # use the simple "Serial No" text field on this row
		row.serial_no = "\n".join(
			frappe.get_all(
				"Serial No",
				filters={"item_code": row.item_code, "warehouse": row.s_warehouse, "status": "Active"},
				order_by="creation asc, name asc",  # FIFO: oldest received first
				limit=cint(row.qty),
				pluck="name",
			)
		)
