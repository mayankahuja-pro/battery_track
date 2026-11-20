// Copyright (c) 2026, Mayank Ahuja and contributors
// For license information, please see license.txt

frappe.query_reports["Battery Trace"] = {
	filters: [
		{
			fieldname: "pack_serial_no",
			label: __("Pack Serial No"),
			fieldtype: "Link",
			options: "Serial No",
			reqd: 1,
			// only show serials of items that have a traceability record (pack items)
			get_query: () => ({ filters: { item_code: "PACK-48V" } }),
		},
	],
};
