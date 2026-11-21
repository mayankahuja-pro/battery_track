"""
Print formats for the warehouse:
  - Pack Label (Serial No): QR sticker that goes ON the battery pack. This is what gets scanned.
  - Pick Sheet (Sales Order): paper for the picker: order QR, what to pick, which packs are on the rack.

Run:  bench --site arb.localhost execute battery_track.setup.print_formats.create
Both are standard (module Battery Track), so developer mode exports them into the app.
"""

import frappe

MODULE = "Battery Track"

# ---------------------------------------------------------------------------
# 1. Pack Label (print from: Serial No -> Print -> Pack Label)
# ---------------------------------------------------------------------------
PACK_LABEL_HTML = """
{% set trace = frappe.db.get_value("Pack Traceability", doc.name,
    ["manufactured_on", "bms_serial_no"], as_dict=True) %}
<div class="label">
  <img class="qr" src="{{ qr_code_data_uri(doc.name, 6) }}">
  <div class="info">
    <div class="brand">ARB ACCESSORIES</div>
    <div class="serial">{{ doc.name }}</div>
    <div class="item">{{ doc.item_name or doc.item_code }}</div>
    <div class="meta">
      {% if trace %}Built {{ frappe.utils.formatdate(trace.manufactured_on) }}<br>BMS {{ trace.bms_serial_no or "-" }}{% endif %}
    </div>
    <div class="hint">Scan this code when picking</div>
  </div>
</div>
"""

PACK_LABEL_CSS = """
.label { width: 90mm; height: 50mm; border: 2px solid #111; border-radius: 3mm; padding: 3mm;
  display: table; font-family: Arial, sans-serif; color: #111; }
.label .qr { display: table-cell; width: 42mm; height: 42mm; vertical-align: middle; }
.label .info { display: table-cell; vertical-align: middle; padding-left: 3mm; }
.label .brand { font-size: 7pt; letter-spacing: 1px; color: #555; font-weight: bold; }
.label .serial { font-size: 17pt; font-weight: bold; margin: 1mm 0; }
.label .item { font-size: 9pt; }
.label .meta { font-size: 7.5pt; color: #444; margin-top: 1.5mm; }
.label .hint { font-size: 6.5pt; color: #777; margin-top: 2mm; border-top: 1px dashed #999; padding-top: 1mm; }
"""

# ---------------------------------------------------------------------------
# 2. Pick Sheet (print from: Sales Order -> Print -> Pick Sheet)
# ---------------------------------------------------------------------------
PICK_SHEET_HTML = """
{% set qr = qr_code_data_uri(doc.name, 4) %}
{% if doc.docstatus != 1 %}
<div class="warn">DRAFT ORDER: do not pick until it is submitted</div>
{% endif %}

<table class="head">
  <tr>
    <td>
      <div class="title">PICK SHEET</div>
      <div class="so">{{ doc.name }}</div>
      <div><b>Customer:</b> {{ doc.customer_name or doc.customer }}</div>
      <div><b>Order date:</b> {{ frappe.utils.formatdate(doc.transaction_date) }}
         &nbsp; <b>Deliver by:</b> {{ frappe.utils.formatdate(doc.delivery_date) }}</div>
      {% if doc.external_order_id %}<div><b>Dealer ref:</b> {{ doc.external_order_id }}</div>{% endif %}
    </td>
    <td class="qrcell">
      <img src="{{ qr }}"><div class="small">Order no. (barcode gun)</div>
    </td>
  </tr>
</table>

<table class="items">
  <thead>
    <tr><th>#</th><th>Item</th><th>Qty</th><th>Scanned</th><th>Packs on the rack (tick what you pick)</th></tr>
  </thead>
  <tbody>
  {% for row in doc.items %}
    {% set scanned = frappe.get_all("Scan Log",
        filters={"sales_order": doc.name, "item_code": row.item_code, "result": "Success"},
        pluck="serial_no") %}
    {% set has_serial = frappe.db.get_value("Item", row.item_code, "has_serial_no") %}
    <tr>
      <td>{{ row.idx }}</td>
      <td><b>{{ row.item_code }}</b><br><span class="small">{{ row.item_name }}</span>
          <br><span class="small">From: {{ row.warehouse or "-" }}</span></td>
      <td class="num">{{ row.qty | int }}</td>
      <td class="num">{{ scanned | length }} / {{ row.qty | int }}</td>
      <td>
        {% if has_serial %}
          {% for s in scanned %}<span class="chip done">&#10003; {{ s }}</span>{% endfor %}
          {% set rack = frappe.get_all("Serial No",
              filters={"item_code": row.item_code, "status": "Active", "warehouse": row.warehouse},
              pluck="name", order_by="name asc", limit=8) %}
          {% for s in rack if s not in scanned %}<span class="chip">&#9744; {{ s }}</span>{% endfor %}
          {% if not rack and not scanned %}<span class="small">No stock in {{ row.warehouse }}</span>{% endif %}
        {% else %}
          <span class="small">No serial: count {{ row.qty | int }} pcs</span>
        {% endif %}
      </td>
    </tr>
  {% endfor %}
  </tbody>
</table>

<div class="steps">
  <b>How to pick</b>
  <ol>
    <li>Open the Battery Scanner app and type the order no. <b>{{ doc.name }}</b>
        (or scan the QR above with a USB barcode gun).</li>
    <li>Take any pack listed above from the rack and scan the <b>QR label on the pack</b>.</li>
    <li>Wait for the &#10003; beep. On &#10007;, put the pack back and read the message.</li>
    <li>When every line shows Qty = Scanned, hand over to dispatch (Delivery Note).</li>
  </ol>
</div>

<table class="sign">
  <tr><td>Picked by</td><td>Checked by</td><td>Date / Time</td></tr>
  <tr class="blank"><td></td><td></td><td></td></tr>
</table>
"""

PICK_SHEET_CSS = """
.warn { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; padding: 6px 10px; font-weight: bold;
  text-align: center; margin-bottom: 8px; }
.head { width: 100%; margin-bottom: 10px; }
.head td { vertical-align: top; }
.head .title { font-size: 9pt; letter-spacing: 2px; color: #666; font-weight: bold; }
.head .so { font-size: 18pt; font-weight: bold; margin: 2px 0 6px; }
.head .qrcell { width: 34mm; text-align: center; }
.head .qrcell img { width: 30mm; height: 30mm; }
.small { font-size: 8pt; color: #555; }
.items { width: 100%; border-collapse: collapse; }
.items th { background: #111; color: #fff; text-align: left; padding: 5px 6px; font-size: 9pt; }
.items td { border-bottom: 1px solid #ddd; padding: 6px; vertical-align: top; font-size: 9.5pt; }
.items .num { text-align: center; font-weight: bold; }
.chip { display: inline-block; border: 1px solid #999; border-radius: 4px; padding: 1px 6px; margin: 2px;
  font-family: monospace; font-size: 9pt; }
.chip.done { background: #dcfce7; border-color: #16a34a; color: #166534; }
.steps { margin: 12px 0; padding: 8px 12px; border: 1px dashed #999; font-size: 9pt; }
.steps ol { margin: 4px 0 0 16px; padding: 0; }
.sign { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 9pt; }
.sign td { border: 1px solid #999; padding: 4px 6px; width: 33%; }
.sign .blank td { height: 14mm; }
"""


def upsert_print_format(name, doc_type, html, css):
	values = {
		"doc_type": doc_type,
		"module": MODULE,
		"standard": "Yes",  # exported into the app (developer mode)
		"custom_format": 1,
		"print_format_type": "Jinja",
		"html": html,
		"css": css,
		"disabled": 0,
	}
	if frappe.db.exists("Print Format", name):
		doc = frappe.get_doc("Print Format", name)
		doc.update(values)
		doc.save()
	else:
		frappe.get_doc({"doctype": "Print Format", "name": name, **values}).insert()


def create():
	upsert_print_format("Pack Label", "Serial No", PACK_LABEL_HTML, PACK_LABEL_CSS)
	upsert_print_format("Pick Sheet", "Sales Order", PICK_SHEET_HTML, PICK_SHEET_CSS)
	frappe.db.commit()
	print("Print formats ready: Pack Label (Serial No), Pick Sheet (Sales Order)")
