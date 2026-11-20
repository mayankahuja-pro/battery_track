"""
Delivery Note doc_events (registered in hooks.py).

Dispatch rule: a serialised item can be dispatched only if that exact serial
was scanned successfully (Scan Log) for the same Sales Order.
"""

import frappe
from frappe import _

from battery_track.events.stock_entry import get_row_serials


def get_scanned_serials(sales_order, item_code):
	"""Serials scanned successfully for this order + item, oldest scan first."""
	return frappe.get_all(
		"Scan Log",
		filters={"sales_order": sales_order, "item_code": item_code, "result": "Success"},
		pluck="serial_no",
		order_by="scanned_at asc",
	)


def is_serialised(item_code):
	# get_cached_value: Item master rarely changes, so read it from cache (faster than a DB hit per row)
	return frappe.get_cached_value("Item", item_code, "has_serial_no")


def before_validate(doc, method=None):
	"""Pre-fill scanned serials on empty rows.

	If we leave serial_no empty, ERPNext auto-picks ANY active serial (FIFO), which may not be
	the pack the warehouse person actually picked. So we put the scanned serials in first.
	"""
	if doc.is_return:
		return  # returns follow a different flow

	for row in doc.items:
		if not row.against_sales_order or not is_serialised(row.item_code):
			continue
		if row.serial_no or row.serial_and_batch_bundle:
			continue  # user already chose serials, don't overwrite

		scanned = get_scanned_serials(row.against_sales_order, row.item_code)
		if len(scanned) >= row.qty:
			row.serial_no = "\n".join(scanned[: int(row.qty)])
		# if fewer are scanned, leave it; before_submit will block with a clear message


def before_submit(doc, method=None):
	"""Block dispatch of any serial that was not scanned for this Sales Order."""
	if doc.is_return:
		return

	for row in doc.items:
		if not row.against_sales_order or not is_serialised(row.item_code):
			continue

		scanned = set(get_scanned_serials(row.against_sales_order, row.item_code))
		dispatching = get_row_serials(row)

		not_scanned = [s for s in dispatching if s not in scanned]
		if not dispatching or not_scanned:
			frappe.throw(
				_("Row {0}: {1} cannot be dispatched. Not scanned for {2}: {3}. Scanned so far: {4}").format(
					row.idx,
					row.item_code,
					row.against_sales_order,
					", ".join(not_scanned) or _("(no serials selected)"),
					", ".join(sorted(scanned)) or _("none"),
				),
				title=_("Scan Required Before Dispatch"),
			)
