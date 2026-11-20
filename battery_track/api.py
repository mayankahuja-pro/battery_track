"""
Public APIs for the dealer system (create_order) and the warehouse scanner (scan_pack).

URL pattern:  POST /api/method/battery_track.api.<function_name>
Auth header:  Authorization: token <api_key>:<api_secret>
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime, nowdate

from battery_track.setup.test_data import COMPANY, FINISHED_GOODS


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
