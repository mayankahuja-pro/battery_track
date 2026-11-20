"""
Battery Trace: full history of one battery pack serial.

Build -> what went inside (BMS + cells) -> which order/customer -> which Delivery Note.
Shown as a simple 2-column "Detail | Value" list, easy to read on screen and in print.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	pack = filters.get("pack_serial_no")
	if not pack:
		return get_columns(), []

	if not frappe.db.exists("Pack Traceability", pack):
		frappe.throw(_("No traceability record for {0}. Was it built with a Manufacture entry?").format(pack))

	data = []
	add_build_section(data, pack)
	add_sales_section(data, pack)
	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "section", "label": _("Stage"), "fieldtype": "Data", "width": 130},
		{"fieldname": "detail", "label": _("Detail"), "fieldtype": "Data", "width": 170},
		# Dynamic Link: the value becomes a clickable link to the doctype named in "link_doctype"
		{"fieldname": "value", "label": _("Value"), "fieldtype": "Dynamic Link", "options": "link_doctype", "width": 260},
		{"fieldname": "link_doctype", "label": _("Type"), "fieldtype": "Data", "width": 140},
	]


def row(section, detail, value, link_doctype=None):
	return {"section": section, "detail": detail, "value": value, "link_doctype": link_doctype}


def add_build_section(data, pack):
	# get_doc: we need the child table (cells), so load the full document
	trace = frappe.get_doc("Pack Traceability", pack)
	status, warehouse = frappe.db.get_value("Serial No", pack, ["status", "warehouse"])

	data.append(row(_("Pack"), _("Pack Serial No"), trace.pack_serial_no, "Serial No"))
	data.append(row(_("Pack"), _("Item"), trace.item_code, "Item"))
	data.append(row(_("Pack"), _("Current Status"), f"{status} {('@ ' + warehouse) if warehouse else ''}"))

	data.append(row(_("Build"), _("Manufactured On"), str(trace.manufactured_on)))
	data.append(row(_("Build"), _("Work Order"), trace.work_order, "Work Order"))
	data.append(row(_("Build"), _("Stock Entry"), trace.stock_entry, "Stock Entry"))

	data.append(row(_("Components"), _("BMS Serial No"), trace.bms_serial_no, "Serial No"))
	for i, cell in enumerate(trace.cells, start=1):
		data.append(row(_("Components"), _("Cell {0}").format(i), cell.cell_serial_no, "Serial No"))


def add_sales_section(data, pack):
	# Which order was this pack scanned (picked) for?
	scan = frappe.db.get_value(
		"Scan Log",
		{"serial_no": pack, "result": "Success"},
		["sales_order", "scanned_by", "scanned_at"],
		as_dict=True,
	)
	if not scan:
		data.append(row(_("Sales"), _("Sales Order"), _("Not picked for any order yet")))
		return

	customer = frappe.db.get_value("Sales Order", scan.sales_order, "customer")
	data.append(row(_("Sales"), _("Sales Order"), scan.sales_order, "Sales Order"))
	data.append(row(_("Sales"), _("Customer"), customer, "Customer"))
	data.append(row(_("Sales"), _("Scanned By"), scan.scanned_by, "User"))
	data.append(row(_("Sales"), _("Scanned At"), str(scan.scanned_at)))

	dn = get_delivery_note(pack)
	if dn:
		data.append(row(_("Dispatch"), _("Delivery Note"), dn.voucher_no, "Delivery Note"))
		data.append(row(_("Dispatch"), _("Dispatched On"), str(dn.posting_datetime)))
	else:
		data.append(row(_("Dispatch"), _("Delivery Note"), _("Not dispatched yet")))


def get_delivery_note(pack):
	"""Find the submitted Delivery Note that shipped this serial.

	v15: a serial's movements live in Serial and Batch Bundle (parent) -> Serial and Batch Entry (child).
	"""
	bundles = frappe.get_all("Serial and Batch Entry", filters={"serial_no": pack}, pluck="parent")
	if not bundles:
		return None

	result = frappe.get_all(
		"Serial and Batch Bundle",
		filters={
			"name": ["in", bundles],
			"voucher_type": "Delivery Note",
			"docstatus": 1,  # submitted
			"is_cancelled": 0,  # not reversed by a cancel
		},
		fields=["voucher_no", "posting_datetime"],
		order_by="posting_datetime desc",
		limit=1,
	)
	return result[0] if result else None
