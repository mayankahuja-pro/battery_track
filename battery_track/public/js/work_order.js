// Work Order: "Build Packs" button (loaded via doctype_js in hooks.py).
// One click builds N packs, but the server still makes ONE Manufacture entry per pack,
// so we always know exactly which cells and BMS went into which pack.
frappe.ui.form.on("Work Order", {
	refresh(frm) {
		const remaining = flt(frm.doc.qty) - flt(frm.doc.produced_qty);
		const open = frm.doc.docstatus === 1 && !["Stopped", "Closed"].includes(frm.doc.status);
		if (!open || remaining <= 0) return;

		frm.add_custom_button(__("Build Packs"), () => {
			frappe.prompt(
				{
					fieldname: "count",
					fieldtype: "Int",
					label: __("How many packs?"),
					default: Math.min(remaining, 20),
					reqd: 1,
					description: __("{0} left to build. One Manufacture entry is made per pack.", [remaining]),
				},
				(values) => {
					frappe
						.call({
							method: "battery_track.api.build_packs",
							args: { work_order: frm.doc.name, count: values.count },
							freeze: true, // block the screen so nobody clicks twice
							freeze_message: __("Building {0} packs...", [values.count]),
						})
						.then((r) => {
							frappe.msgprint({ title: __("Packs built"), message: r.message.message, indicator: "green" });
							frm.reload_doc(); // show the new produced qty
						});
				},
				__("Build Packs"),
				__("Build")
			);
		});
	},
});
