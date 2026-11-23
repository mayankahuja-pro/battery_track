// Delivery Note: "Pack QR Codes" button (loaded via doctype_js in hooks.py).
// Shows a QR for every pack to pick, so the warehouse person can scan them with the app
// (from the screen or from a printout). Scanned packs show a green tick.
frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.doc.is_return) return; // only while picking (draft)

		frm.add_custom_button(__("Pack QR Codes"), () => {
			if (frm.is_new()) {
				frappe.msgprint(__("Please save the Delivery Note first."));
				return;
			}
			frappe
				.call({ method: "battery_track.api.get_pack_qr_codes", args: { delivery_note: frm.doc.name } })
				.then((r) => show_qr_dialog(frm, r.message));
		});
	},
});

function show_qr_dialog(frm, data) {
	const esc = frappe.utils.escape_html; // never put DB text into HTML without escaping

	if (!data.rows.length) {
		frappe.msgprint(__("No serialised items linked to a Sales Order in this Delivery Note."));
		return;
	}

	// 1. order QR(s): the app needs the Sales Order number first
	let html = `<div class="bt-qr-grid">`;
	data.orders.forEach((o) => {
		html += `<div class="bt-qr bt-order"><img src="${o.qr}"><b>${esc(o.sales_order)}</b>
			<small>${__("Sales Order: scan first")}</small></div>`;
	});
	html += `</div>`;

	// 2. one block per item row, one card per pack
	data.rows.forEach((row) => {
		const done = row.packs.filter((p) => p.scanned).length;
		html += `<h5 style="margin-top:16px">${__("Row {0}", [row.idx])}: ${esc(row.item_code)}
			&nbsp; <span class="text-muted">${__("Scanned {0} / {1}", [done, row.qty])}</span></h5>`;
		if (row.short > 0) {
			html += `<div class="text-danger">${__("{0} more pack(s) needed, not in stock in {1}", [
				row.short,
				esc(row.warehouse),
			])}</div>`;
		}
		html += `<div class="bt-qr-grid">`;
		row.packs.forEach((p) => {
			html += `<div class="bt-qr ${p.scanned ? "bt-done" : ""}"><img src="${p.qr}">
				<b>${esc(p.serial_no)}</b><small>${p.scanned ? "&#10003; " + __("Scanned") : __("To scan")}</small></div>`;
		});
		html += `</div>`;
	});

	const css = `<style>
		.bt-qr-grid { display: flex; flex-wrap: wrap; gap: 10px; }
		.bt-qr { width: 150px; border: 1px solid #ccc; border-radius: 8px; padding: 8px; text-align: center;
			display: flex; flex-direction: column; align-items: center; page-break-inside: avoid; }
		.bt-qr img { width: 130px; height: 130px; }
		.bt-qr small { color: #666; }
		.bt-done { background: #dcfce7; border-color: #16a34a; }
		.bt-order { border: 2px solid #111; }
	</style>`;

	const d = new frappe.ui.Dialog({
		title: __("Pack QR Codes for {0}", [frm.doc.name]),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "qrs", options: css + html }],
		primary_action_label: __("Print"),
		primary_action() {
			// open the same HTML in a new tab and print it (labels for the rack)
			const w = window.open("", "_blank");
			w.document.write(`<html><head><title>${esc(frm.doc.name)}</title>${css}</head>
				<body style="font-family: sans-serif">${html}</body></html>`);
			w.document.close();
			w.onload = () => w.print();
		},
		secondary_action_label: __("Refresh"),
		secondary_action() {
			d.hide();
			frappe
				.call({ method: "battery_track.api.get_pack_qr_codes", args: { delivery_note: frm.doc.name } })
				.then((r) => show_qr_dialog(frm, r.message)); // see new ticks after scanning
		},
	});
	d.show();
}
