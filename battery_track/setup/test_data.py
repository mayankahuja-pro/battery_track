"""
Test master data for Battery Track.

Run:   bench --site arb.localhost execute battery_track.setup.test_data.create
Check: bench --site arb.localhost execute battery_track.setup.test_data.check

The script is safe to run many times: it skips any record that already exists.
"""

import frappe

COMPANY = "ARB Accessories Pvt. Ltd"
STORES = "Stores - AAPL"  # raw material warehouse (created by ERPNext setup wizard)
FINISHED_GOODS = "Finished Goods - AAPL"  # finished pack warehouse

# item_code is short (easy to type in curl / API calls), item_name is the readable name
ITEMS = [
	{
		"item_code": "CELL-32V",
		"item_name": "Li-ion Cell 3.2V",
		"item_group": "Raw Material",
		"has_serial_no": 1,
		"serial_no_series": "CELL-.####",  # auto serials like CELL-0001
		"default_warehouse": STORES,
		"standard_rate": 250,
	},
	{
		"item_code": "BMS-16S",
		"item_name": "BMS 16S",
		"item_group": "Raw Material",
		"has_serial_no": 1,
		"serial_no_series": "BMS-.####",
		"default_warehouse": STORES,
		"standard_rate": 1800,
	},
	{
		"item_code": "CASING",
		"item_name": "Battery Casing",
		"item_group": "Raw Material",
		"has_serial_no": 0,  # casing is cheap, no need to track each piece
		"default_warehouse": STORES,
		"standard_rate": 500,
	},
	{
		"item_code": "PACK-48V",
		"item_name": "48V Battery Pack",
		"item_group": "Products",
		"has_serial_no": 1,
		"serial_no_series": "PACK-.####",  # Work Order will auto-create PACK-0001
		"default_warehouse": FINISHED_GOODS,
		"standard_rate": 12000,
	},
]


def create():
	"""Create items, supplier and customer (skip if they already exist)."""
	for item in ITEMS:
		create_item(item)

	create_supplier()
	create_customer()

	frappe.db.commit()  # bench execute does not auto-commit, so save explicitly
	print("Test data ready.")


def create_item(data):
	# frappe.db.exists returns the name if found, else None (cheap check, no full doc load)
	if frappe.db.exists("Item", data["item_code"]):
		print(f"Item {data['item_code']} already exists, skipping")
		return

	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": data["item_code"],
			"item_name": data["item_name"],
			"item_group": data["item_group"],
			"stock_uom": "Nos",
			"is_stock_item": 1,  # we keep stock of it in a warehouse
			"has_serial_no": data["has_serial_no"],
			"serial_no_series": data.get("serial_no_series"),
			"standard_rate": data["standard_rate"],
			# Item Defaults child table: default warehouse per company
			"item_defaults": [{"company": COMPANY, "default_warehouse": data["default_warehouse"]}],
		}
	)
	item.insert()
	print(f"Created Item {item.name}")


def create_supplier():
	name = "Shenzhen Cell Co."
	if frappe.db.exists("Supplier", name):
		print(f"Supplier {name} already exists, skipping")
		return

	frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": name,
			"supplier_group": "Raw Material",
			"supplier_type": "Company",
			"country": "China",
		}
	).insert()
	print(f"Created Supplier {name}")


def create_customer():
	name = "Sharma EV Dealers"
	if frappe.db.exists("Customer", name):
		print(f"Customer {name} already exists, skipping")
		return

	frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Company",  # B2B dealer
			"customer_group": "Commercial",
			"territory": "India",
		}
	).insert()
	print(f"Created Customer {name}")


API_USER = "scanner@example.com"


def create_api_user():
	"""Create an API user with only the roles it needs, and print a fresh key + secret.

	Run: bench --site arb.localhost execute battery_track.setup.test_data.create_api_user
	Running it again gives a NEW secret (the old one stops working).
	"""
	if not frappe.db.exists("User", API_USER):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": API_USER,
				"first_name": "Warehouse Scanner",
				"send_welcome_email": 0,
				"user_type": "System User",
				# least privilege: Sales User to create orders, Stock User to scan
				"roles": [{"role": "Sales User"}, {"role": "Stock User"}],
			}
		)
		user.insert(ignore_permissions=True)

	user = frappe.get_doc("User", API_USER)
	if not user.api_key:
		user.api_key = frappe.generate_hash(length=15)
	api_secret = frappe.generate_hash(length=15)
	user.api_secret = api_secret  # stored encrypted (Password field)
	user.save(ignore_permissions=True)
	frappe.db.commit()

	print(f"api_key    = {user.api_key}")
	print(f"api_secret = {api_secret}")
	print(f'Header: "Authorization: token {user.api_key}:{api_secret}"')


def set_api_user_password(password="Scanner@2026"):
	"""Give the scanner user a password, for the app's ID/password login.

	Run: bench --site arb.localhost execute battery_track.setup.test_data.set_api_user_password
	Demo password only: change it in a real setup.
	"""
	from frappe.utils.password import update_password

	update_password(API_USER, password)  # stored hashed, never in plain text
	frappe.db.commit()
	print(f"Password set for {API_USER}")


def check():
	"""Print what exists, so we can verify quickly."""
	print("Warehouses:", frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name"))
	print(
		"Items:",
		frappe.get_all("Item", fields=["name", "item_name", "has_serial_no", "serial_no_series"]),
	)
	print("Suppliers:", frappe.get_all("Supplier", pluck="name"))
	print("Customers:", frappe.get_all("Customer", pluck="name"))
