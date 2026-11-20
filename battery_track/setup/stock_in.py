"""
Step 2: Stock comes in from the China supplier.

Run:   bench --site arb.localhost execute battery_track.setup.stock_in.create_purchase_receipt
Check: bench --site arb.localhost execute battery_track.setup.stock_in.check
"""

import frappe

from battery_track.setup.test_data import COMPANY, STORES

SUPPLIER = "Shenzhen Cell Co."


def make_serials(prefix, count):
	"""make_serials("CELL", 3) -> "CELL-0001\nCELL-0002\nCELL-0003" """
	return "\n".join(f"{prefix}-{i:04d}" for i in range(1, count + 1))


def create_purchase_receipt():
	# If CELL-0001 already exists, the stock has already been received: don't receive it twice
	if frappe.db.exists("Serial No", "CELL-0001"):
		print("Serial CELL-0001 already exists, Purchase Receipt was already made. Skipping.")
		return

	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"company": COMPANY,
			"supplier": SUPPLIER,
			"set_warehouse": STORES,  # all items go to Stores
			"items": [
				# serial_no is a newline-separated list. Because "Use Serial / Batch Fields"
				# is ON in Stock Settings, ERPNext converts it into a Serial and Batch Bundle on submit.
				{"item_code": "CELL-32V", "qty": 20, "rate": 250, "serial_no": make_serials("CELL", 20)},
				{"item_code": "BMS-16S", "qty": 2, "rate": 1800, "serial_no": make_serials("BMS", 2)},
				{"item_code": "CASING", "qty": 2, "rate": 500},  # no serial for casing
			],
		}
	)
	pr.insert()
	pr.submit()  # submit = stock actually moves (Stock Ledger + GL entries are created)
	frappe.db.commit()
	print(f"Submitted {pr.name}, grand total {pr.grand_total}")


def receive_cells(start=21, count=12, rate=250):
	"""Receive more cells (e.g. to build another pack for a demo).

	bench --site arb.localhost execute battery_track.setup.stock_in.receive_cells --kwargs "{'start': 21, 'count': 12}"
	"""
	serials = [f"CELL-{i:04d}" for i in range(start, start + count)]
	if frappe.db.exists("Serial No", serials[0]):
		print(f"{serials[0]} already exists, skipping")
		return

	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"company": COMPANY,
			"supplier": SUPPLIER,
			"set_warehouse": STORES,
			"items": [{"item_code": "CELL-32V", "qty": count, "rate": rate, "serial_no": "\n".join(serials)}],
		}
	)
	pr.insert()
	pr.submit()
	frappe.db.commit()
	print(f"Submitted {pr.name}: {serials[0]} .. {serials[-1]}")


def check():
	"""Show serial status and stock balance in Stores."""
	serials = frappe.get_all(
		"Serial No",
		fields=["name", "item_code", "status", "warehouse"],
		order_by="name",
	)
	for s in serials:
		print(s.name, s.item_code, s.status, s.warehouse)

	# Bin = current stock qty per item per warehouse
	print("\nStock in Stores:")
	for b in frappe.get_all("Bin", filters={"warehouse": STORES}, fields=["item_code", "actual_qty"]):
		print(b.item_code, b.actual_qty)
