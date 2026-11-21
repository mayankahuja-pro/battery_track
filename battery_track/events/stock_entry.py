"""
Stock Entry doc_events (registered in hooks.py).

When a "Manufacture" Stock Entry is submitted, we save which cells and which BMS
went into the pack, in a Pack Traceability record.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime

from erpnext.stock.serial_batch_bundle import get_serial_nos

# Which raw material is a "cell" and which is a "BMS".
# Kept as constants for simplicity (one pack model in this project).
CELL_ITEM = "CELL-32V"
BMS_ITEM = "BMS-16S"


def get_row_serials(row):
	"""Return the list of serial numbers on one Stock Entry row.

	In v15 serials live in a Serial and Batch Bundle. With "Use Serial / Batch Fields"
	ON they are also copied into row.serial_no, so we read the bundle first and fall back to the text.
	"""
	if row.serial_and_batch_bundle:
		return get_serial_nos(row.serial_and_batch_bundle)
	if row.serial_no:
		return row.serial_no.split("\n")

	# Serial left empty in the form: on submit ERPNext auto-creates the serials (from the item's
	# series, e.g. PACK-0003) or auto-picks them (FIFO for cells). It links that bundle to the
	# Stock Ledger Entry, not to our in-memory row, so look it up by the row's name.
	bundle = frappe.db.get_value(
		"Serial and Batch Bundle",
		{
			"voucher_type": row.parenttype,
			"voucher_no": row.parent,
			"voucher_detail_no": row.name,  # this exact row
			"is_cancelled": 0,
		},
		"name",
	)
	return get_serial_nos(bundle) if bundle else []


def get_finished_pack_rows(doc):
	"""Finished-good rows whose item has serial numbers (e.g. 48V Battery Pack)."""
	return [
		row
		for row in doc.items
		if row.is_finished_item and frappe.get_cached_value("Item", row.item_code, "has_serial_no")
	]


def before_submit(doc, method=None):
	"""Block a manufacture entry that builds more than 1 serialised pack.

	If one entry builds 2 packs from 32 cells, we cannot know which 16 cells went into which pack.
	So for correct traceability, build one pack per entry.
	"""
	if doc.purpose != "Manufacture":
		return

	for row in get_finished_pack_rows(doc):
		if row.qty != 1:
			frappe.throw(
				_("Row {0}: build one {1} per Manufacture entry (qty is {2}), so cell traceability stays correct.").format(
					row.idx, row.item_code, row.qty
				)
			)


def on_submit(doc, method=None):
	"""Create the Pack Traceability record after a Manufacture entry is submitted."""
	if doc.purpose != "Manufacture":
		return  # Material Receipt / Transfer etc. are not our business

	pack_rows = get_finished_pack_rows(doc)
	if not pack_rows:
		return  # finished item has no serial no, nothing to trace

	pack_row = pack_rows[0]  # before_submit already made sure qty is 1
	pack_serials = get_row_serials(pack_row)
	if not pack_serials:
		# never crash with IndexError: tell the user what is missing
		frappe.throw(_("Row {0}: no serial number found for {1}. Enter it in the Serial No field.").format(
			pack_row.idx, pack_row.item_code))
	pack_serial = pack_serials[0]

	# collect cell and BMS serials from the raw material rows (rows that go OUT of a warehouse)
	cell_serials = []
	bms_serial = None
	for row in doc.items:
		if not row.s_warehouse:
			continue  # not a consumed raw material
		if row.item_code == CELL_ITEM:
			cell_serials.extend(get_row_serials(row))
		elif row.item_code == BMS_ITEM:
			bms_serials = get_row_serials(row)
			bms_serial = bms_serials[0] if bms_serials else None

	trace = frappe.get_doc(
		{
			"doctype": "Pack Traceability",
			"pack_serial_no": pack_serial,
			"item_code": pack_row.item_code,
			"stock_entry": doc.name,
			"work_order": doc.work_order,
			"bms_serial_no": bms_serial,
			"manufactured_on": get_datetime(f"{doc.posting_date} {doc.posting_time}"),
			"cells": [{"cell_serial_no": s} for s in cell_serials],
		}
	)
	# ignore_permissions: this is a system record created by the hook. The store user who
	# submits the Stock Entry may not have "create" rights on Pack Traceability.
	trace.insert(ignore_permissions=True)

	frappe.msgprint(_("Pack Traceability {0} created").format(trace.name), alert=True)


def on_cancel(doc, method=None):
	"""Manufacture entry cancelled = pack was never built, so remove its traceability record."""
	if doc.purpose != "Manufacture":
		return

	for name in frappe.get_all("Pack Traceability", filters={"stock_entry": doc.name}, pluck="name"):
		frappe.delete_doc("Pack Traceability", name, ignore_permissions=True)
