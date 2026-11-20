"""
Step 3: Build one 48V Battery Pack.

Run in order:
  bench --site arb.localhost execute battery_track.setup.manufacture.create_bom
  bench --site arb.localhost execute battery_track.setup.manufacture.create_work_order
  bench --site arb.localhost execute battery_track.setup.manufacture.make_manufacture_entry --kwargs "{'work_order': 'MFG-WO-2026-00001'}"
"""

import frappe

from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

from battery_track.setup.test_data import COMPANY, FINISHED_GOODS, STORES

PACK_ITEM = "PACK-48V"


def create_bom():
	"""BOM = recipe: 1 pack needs 16 cells + 1 BMS + 1 casing."""
	existing = frappe.db.get_value("BOM", {"item": PACK_ITEM, "is_default": 1, "docstatus": 1})
	if existing:
		print(f"Default BOM {existing} already exists, skipping")
		return existing

	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": PACK_ITEM,
			"company": COMPANY,
			"quantity": 1,  # recipe for 1 pack
			"rm_cost_as_per": "Valuation Rate",  # cost from the actual purchase rate
			"items": [
				{"item_code": "CELL-32V", "qty": 16},
				{"item_code": "BMS-16S", "qty": 1},
				{"item_code": "CASING", "qty": 1},
			],
		}
	)
	bom.insert()
	bom.submit()  # only a submitted BOM can be used in a Work Order
	frappe.db.commit()
	print(f"Created BOM {bom.name}, cost per pack: {bom.total_cost}")
	return bom.name


def create_work_order(qty=1):
	"""Work Order = instruction to the shop floor: build <qty> packs using this BOM."""
	bom = frappe.db.get_value("BOM", {"item": PACK_ITEM, "is_default": 1, "docstatus": 1})

	wo = frappe.get_doc(
		{
			"doctype": "Work Order",
			"company": COMPANY,
			"production_item": PACK_ITEM,
			"bom_no": bom,
			"qty": qty,
			# skip_transfer: take raw material straight from Stores during "Manufacture".
			# (Otherwise we first need a "Material Transfer for Manufacture" to the WIP warehouse.)
			"skip_transfer": 1,
			"source_warehouse": STORES,
			"wip_warehouse": STORES,
			"fg_warehouse": FINISHED_GOODS,
		}
	)
	wo.insert()
	wo.submit()
	frappe.db.commit()
	print(f"Created Work Order {wo.name} for {qty} x {PACK_ITEM}")
	return wo.name


def make_manufacture_entry(work_order, pack_serial="PACK-0001", cell_serials=None, bms_serial="BMS-0001"):
	"""Create + submit the Manufacture Stock Entry. Our on_submit hook then creates Pack Traceability.

	We choose the exact cell / BMS serials (what the worker physically picked).
	"""
	if cell_serials is None:
		cell_serials = [f"CELL-{i:04d}" for i in range(1, 17)]  # CELL-0001 .. CELL-0016

	# ERPNext's own function: builds the Stock Entry rows from the Work Order + BOM
	se = frappe.get_doc(make_stock_entry(work_order, "Manufacture", 1))

	for row in se.items:
		if row.item_code == "CELL-32V":
			row.serial_no = "\n".join(cell_serials)
		elif row.item_code == "BMS-16S":
			row.serial_no = bms_serial
		elif row.item_code == PACK_ITEM:
			row.serial_no = pack_serial  # serial for the new pack

	se.insert()
	se.submit()  # -> stock moves + our hook runs
	frappe.db.commit()
	print(f"Submitted Stock Entry {se.name}")
	return se.name


def check(pack_serial="PACK-0001"):
	"""Print the Pack Traceability record for a pack."""
	if not frappe.db.exists("Pack Traceability", pack_serial):
		print(f"No Pack Traceability for {pack_serial}")
		return

	trace = frappe.get_doc("Pack Traceability", pack_serial)
	print("Pack:", trace.pack_serial_no, "| BMS:", trace.bms_serial_no)
	print("Stock Entry:", trace.stock_entry, "| Work Order:", trace.work_order, "| On:", trace.manufactured_on)
	print("Cells:", [c.cell_serial_no for c in trace.cells])
	print("Pack serial status:", frappe.db.get_value("Serial No", pack_serial, ["status", "warehouse"]))
