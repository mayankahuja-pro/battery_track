"""
Battery Track workspace: one page in ERPNext with counters, charts, shortcuts and reports.

Run:  bench --site arb.localhost execute battery_track.setup.workspace.create

Running it again updates the records (no duplicates). Because developer_mode is on, the
Number Cards, Dashboard Charts and Workspace are exported as JSON into the app.
The Custom HTML Block (hero banner) has no module, so it ships through fixtures (hooks.py).
"""

import json

import frappe

MODULE = "Battery Track"
PACK = "PACK-48V"
HERO_BLOCK = "Battery Track Hero"


def upsert(doctype, name, values):
	"""Create the record, or update it if it already exists. Returns the doc."""
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		for child_table in ("links", "shortcuts", "charts", "number_cards", "quick_lists", "custom_blocks"):
			if child_table in values:
				doc.set(child_table, [])  # replace child rows instead of adding duplicates
		doc.update(values)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.insert()
	return doc


def f(doctype, field, op, value):
	"""One filter row in the format Number Cards / Charts store: [doctype, field, op, value, false]."""
	return [doctype, field, op, value, False]


# ---------------------------------------------------------------------------
# 1. Number cards (the big counters)
# ---------------------------------------------------------------------------
NUMBER_CARDS = [
	("Packs Built", "Pack Traceability", [], "#16a34a"),
	("Packs In Stock", "Serial No", [f("Serial No", "item_code", "=", PACK), f("Serial No", "status", "=", "Active")], "#0ea5e9"),
	("Packs Dispatched", "Serial No", [f("Serial No", "item_code", "=", PACK), f("Serial No", "status", "=", "Delivered")], "#6366f1"),
	(
		"Orders To Pick",
		"Sales Order",
		[f("Sales Order", "docstatus", "=", 1), f("Sales Order", "status", "in", ["To Deliver and Bill", "To Deliver"])],
		"#f59e0b",
	),
	("Cells In Stores", "Serial No", [f("Serial No", "item_code", "=", "CELL-32V"), f("Serial No", "status", "=", "Active")], "#14b8a6"),
	("BMS In Stores", "Serial No", [f("Serial No", "item_code", "=", "BMS-16S"), f("Serial No", "status", "=", "Active")], "#8b5cf6"),
	("Scans Today", "Scan Log", [f("Scan Log", "result", "=", "Success"), f("Scan Log", "creation", "Timespan", "today")], "#22c55e"),
	("Scan Errors Today", "Scan Log", [f("Scan Log", "result", "=", "Error"), f("Scan Log", "creation", "Timespan", "today")], "#ef4444"),
]


def create_number_cards():
	for label, doctype, filters, color in NUMBER_CARDS:
		upsert(
			"Number Card",
			label,
			{
				"name": label,
				"label": label,
				"type": "Document Type",
				"document_type": doctype,
				"function": "Count",
				"filters_json": json.dumps(filters),
				"color": color,
				"is_public": 1,
				"is_standard": 1,  # exported into the app (developer mode)
				"module": MODULE,
			},
		)


# ---------------------------------------------------------------------------
# 2. Dashboard charts
# ---------------------------------------------------------------------------
CHARTS = [
	# timeseries: count per day/week
	dict(chart_name="Daily Scans", chart_type="Count", document_type="Scan Log", based_on="scanned_at",
		 timeseries=1, timespan="Last Month", time_interval="Daily", type="Bar", color="#22c55e",
		 filters_json=json.dumps([f("Scan Log", "result", "=", "Success")])),
	dict(chart_name="Packs Built Per Week", chart_type="Count", document_type="Pack Traceability",
		 based_on="manufactured_on", timeseries=1, timespan="Last Quarter", time_interval="Weekly",
		 type="Line", color="#16a34a", filters_json="[]"),
	# group by: share of each value
	dict(chart_name="Scan Results", chart_type="Group By", document_type="Scan Log", group_by_based_on="result",
		 group_by_type="Count", type="Donut", filters_json="[]"),
	dict(chart_name="Pack Status", chart_type="Group By", document_type="Serial No", group_by_based_on="status",
		 group_by_type="Count", type="Donut", filters_json=json.dumps([f("Serial No", "item_code", "=", PACK)])),
	dict(chart_name="Scans By User", chart_type="Group By", document_type="Scan Log",
		 group_by_based_on="scanned_by", group_by_type="Count", type="Bar", color="#0ea5e9", filters_json="[]"),
	dict(chart_name="Cell Status", chart_type="Group By", document_type="Serial No", group_by_based_on="status",
		 group_by_type="Count", type="Pie", filters_json=json.dumps([f("Serial No", "item_code", "=", "CELL-32V")])),
]


def create_charts():
	for chart in CHARTS:
		doc = upsert(
			"Dashboard Chart",
			chart["chart_name"],
			{"name": chart["chart_name"], "is_public": 1, "is_standard": 1, "module": MODULE, **chart},
		)
		# On insert Frappe fills empty fields with defaults, so "currency" became INR and the
		# charts showed "₹ 30.00" for 30 scans. These are counts, not money: clear it.
		if doc.currency:
			doc.currency = None
			doc.save()


# ---------------------------------------------------------------------------
# 3. Hero banner (Custom HTML Block)
# ---------------------------------------------------------------------------
HERO_HTML = """
<div class="hero">
  <div class="hero-text">
    <div class="eyebrow">ARB ACCESSORIES • PACK TRACEABILITY</div>
    <h1>🔋 Battery Track</h1>
    <p>Every cell, every BMS, every pack: from the China supplier to the dealer.</p>
    <form class="trace">
      <input placeholder="Trace a pack, e.g. PACK-0001" autocomplete="off" />
      <button type="submit">Trace →</button>
    </form>
  </div>
  <div class="flow">
    <a data-route="List/Purchase Receipt"><span>📦</span>Stock In</a>
    <a data-route="List/Work Order"><span>🏭</span>Build</a>
    <a data-route="List/Sales Order"><span>🧾</span>Order</a>
    <a data-route="List/Scan Log"><span>📷</span>Scan</a>
    <a data-route="List/Delivery Note"><span>🚚</span>Dispatch</a>
    <a data-route="query-report/Battery Trace"><span>🔍</span>Trace</a>
  </div>
</div>
"""

HERO_STYLE = """
.hero { display: flex; flex-wrap: wrap; gap: 20px; align-items: center; justify-content: space-between;
  padding: 26px 28px; border-radius: 16px; color: #fff;
  background: radial-gradient(circle at 92% 10%, rgba(250,204,21,.30), transparent 35%),
              radial-gradient(circle at 5% 100%, rgba(14,165,233,.40), transparent 40%),
              linear-gradient(135deg, #052e16 0%, #166534 45%, #0f172a 100%); }
.hero-text { flex: 1 1 320px; }
.eyebrow { font-size: 11px; letter-spacing: .2em; font-weight: 700; color: #bbf7d0; }
h1 { margin: 6px 0 4px; font-size: 30px; font-weight: 800; color: #fff; }
p { margin: 0 0 16px; color: #dcfce7; font-size: 14px; }
.trace { display: flex; gap: 8px; max-width: 420px; }
.trace input { flex: 1; min-width: 0; padding: 10px 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,.3);
  background: rgba(255,255,255,.12); color: #fff; font-size: 14px; outline: none; }
.trace input::placeholder { color: #bbf7d0; }
.trace input:focus { border-color: #fde68a; background: rgba(255,255,255,.18); }
.trace button { padding: 10px 16px; border: 0; border-radius: 10px; background: #facc15; color: #1f2937;
  font-weight: 700; cursor: pointer; }
.trace button:hover { background: #fde047; }
.flow { display: grid; grid-template-columns: repeat(3, 92px); gap: 10px; }
.flow a { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 12px 6px;
  border-radius: 12px; background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.18);
  color: #fff; font-size: 12px; font-weight: 600; cursor: pointer; text-decoration: none; transition: .15s; }
.flow a:hover { background: rgba(255,255,255,.22); transform: translateY(-2px); }
.flow span { font-size: 22px; }
@media (max-width: 600px) { .flow { grid-template-columns: repeat(3, 1fr); width: 100%; } }
"""

# root_element is given by Frappe: the block's own (shadow) root, so querySelector only sees our HTML
HERO_SCRIPT = """
root_element.querySelectorAll('.flow a').forEach((link) => {
  link.addEventListener('click', () => frappe.set_route(link.dataset.route));
});

root_element.querySelector('.trace').addEventListener('submit', (event) => {
  event.preventDefault();
  const serial = root_element.querySelector('.trace input').value.trim().toUpperCase();
  if (!serial) return;
  frappe.set_route('query-report', 'Battery Trace', { pack_serial_no: serial });
});
"""


def create_hero_block():
	upsert(
		"Custom HTML Block",
		HERO_BLOCK,
		{"name": HERO_BLOCK, "html": HERO_HTML, "style": HERO_STYLE, "script": HERO_SCRIPT, "private": 0},
	)


# ---------------------------------------------------------------------------
# 4. Workspace (the page that puts everything together)
# ---------------------------------------------------------------------------
def block(block_type, col, **data):
	"""One block in the workspace layout. col = width out of 12."""
	return {"id": frappe.generate_hash(length=10), "type": block_type, "data": {**data, "col": col}}


def header(text):
	return block("header", 12, text=f'<span class="h4"><b>{text}</b></span>')


SHORTCUTS = [
	# label, type, link_to, color, doc_view, stats_filter, format
	("Battery Trace", "Report", "Battery Trace", "Green", "", None, None),
	("Pack Traceability", "DocType", "Pack Traceability", "Blue", "List", None, None),
	("Scan Log", "DocType", "Scan Log", "Red", "List", {"result": "Error"}, "{} Errors"),
	("Sales Order", "DocType", "Sales Order", "Orange", "List",
	 {"docstatus": 1, "status": ["in", ["To Deliver and Bill", "To Deliver"]]}, "{} To Pick"),
	("New Work Order", "DocType", "Work Order", "Purple", "New", None, None),
	("Delivery Note", "DocType", "Delivery Note", "Cyan", "List", None, None),
	("Serial No", "DocType", "Serial No", "Grey", "List", {"item_code": PACK, "status": "Active"}, "{} Packs Active"),
	("Stock Ledger", "Report", "Stock Ledger", "Yellow", "", None, None),
]

LINK_CARDS = [
	("Traceability", [("Report", "Battery Trace", 1), ("DocType", "Pack Traceability", 0), ("DocType", "Scan Log", 0)]),
	("Stock In", [("DocType", "Purchase Receipt", 0), ("DocType", "Supplier", 0), ("DocType", "Item", 0)]),
	("Manufacturing", [("DocType", "BOM", 0), ("DocType", "Work Order", 0), ("DocType", "Stock Entry", 0)]),
	("Selling & Dispatch", [("DocType", "Sales Order", 0), ("DocType", "Delivery Note", 0), ("DocType", "Customer", 0)]),
	("Stock Reports", [("Report", "Stock Balance", 1), ("Report", "Stock Ledger", 1),
					   ("Report", "Serial No Ledger", 1), ("Report", "Serial and Batch Summary", 1)]),
]

QUICK_LISTS = [
	("Recent Scan Errors", "Scan Log", [f("Scan Log", "result", "=", "Error")]),
	("Recently Built Packs", "Pack Traceability", []),
]


def create_workspace():
	content = [block("custom_block", 12, custom_block_name=HERO_BLOCK), block("spacer", 12)]

	content.append(header("📊 Live Numbers"))
	content += [block("number_card", 3, number_card_name=label) for label, *_ in NUMBER_CARDS]

	content.append(header("📈 Charts"))
	content += [
		block("chart", 8, chart_name="Daily Scans"),
		block("chart", 4, chart_name="Scan Results"),
		block("chart", 8, chart_name="Packs Built Per Week"),
		block("chart", 4, chart_name="Pack Status"),
		block("chart", 6, chart_name="Scans By User"),
		block("chart", 6, chart_name="Cell Status"),
	]

	content.append(header("⚡ Quick Access"))
	content += [block("shortcut", 3, shortcut_name=s[0]) for s in SHORTCUTS]

	content.append(header("🕒 Recent Activity"))
	content += [block("quick_list", 6, quick_list_name=label) for label, *_ in QUICK_LISTS]

	content.append(header("📚 Masters, Transactions & Reports"))
	content += [block("card", 4, card_name=name) for name, _ in LINK_CARDS]

	links = []
	for card_name, items in LINK_CARDS:
		links.append({"type": "Card Break", "label": card_name, "link_count": len(items)})
		for link_type, link_to, is_report in items:
			links.append({"type": "Link", "label": link_to, "link_type": link_type, "link_to": link_to,
						  "is_query_report": is_report, "onboard": 0})

	upsert(
		"Workspace",
		"Battery Track",
		{
			"name": "Battery Track",
			"label": "Battery Track",
			"title": "Battery Track",
			"module": MODULE,
			"icon": "stock",
			"indicator_color": "green",
			"public": 1,
			"sequence_id": 1,  # near the top of the sidebar
			"content": json.dumps(content),
			"number_cards": [{"number_card_name": label, "label": label} for label, *_ in NUMBER_CARDS],
			"charts": [{"chart_name": c["chart_name"], "label": c["chart_name"]} for c in CHARTS],
			"custom_blocks": [{"custom_block_name": HERO_BLOCK, "label": HERO_BLOCK}],
			"shortcuts": [
				{"label": label, "type": stype, "link_to": link_to, "color": color, "doc_view": view,
				 "stats_filter": json.dumps(stats) if stats else None, "format": fmt}
				for label, stype, link_to, color, view, stats, fmt in SHORTCUTS
			],
			"quick_lists": [
				{"label": label, "document_type": doctype, "quick_list_filter": json.dumps(filters)}
				for label, doctype, filters in QUICK_LISTS
			],
			"links": links,
		},
	)


def create():
	create_number_cards()
	create_charts()
	create_hero_block()
	create_workspace()
	frappe.db.commit()
	print("Battery Track workspace ready: /app/battery-track")
