# Battery Track

Serial-number traceability for lithium-ion battery packs, built on **Frappe / ERPNext v15**.

A battery importer and pack assembler needs to answer one question fast: *"This pack failed. Which cells and which BMS are inside it, when was it built, and which dealer has it?"* Battery Track answers it by connecting standard ERPNext documents and adding three small rules.

```
Stock in  ->  Build pack  ->  Order in (API)  ->  Scan to pick  ->  Dispatch  ->  Trace anytime
(Purchase    (BOM + Work      (Sales Order,       (Scan API +       (Delivery     (Battery Trace
 Receipt)     Order + hook)    idempotent)         Scan Log)         Note rule)     report)
```

## What it does

| Stage | Standard ERPNext | What this app adds |
|---|---|---|
| Stock in | Purchase Receipt with serial numbers (Serial and Batch Bundle) | Script to create test receipts |
| Build | BOM (16 cells + 1 BMS + 1 casing) -> Work Order -> Manufacture Stock Entry | `Stock Entry` hook saves a **Pack Traceability** record with the pack, BMS and cell serials |
| Order in | Sales Order | `create_order` API, idempotent on `external_order_id` |
| Pick | (none) | `scan_pack` API with 5 validations; every scan stored in **Scan Log** |
| Dispatch | Delivery Note | Hook: only serials scanned for that Sales Order can be dispatched |
| Trace | (none) | **Battery Trace** script report |

The app uses standard documents wherever ERPNext already has one, and customises only where the business needs a rule that ERPNext does not enforce.

## Design decisions

- **One pack per Manufacture entry.** If one entry builds two packs from 32 cells, nobody can say which 16 cells went into which pack. A `before_submit` hook blocks qty > 1 for serialised packs.
- **Cancel removes the trace.** If the Manufacture entry is cancelled, the pack was never built, so its Pack Traceability record is deleted.
- **Idempotent order API.** A custom field `external_order_id` on Sales Order (unique, no_copy) means a retried request returns the existing order instead of creating a duplicate. The unique DB index also covers two requests arriving at the same moment.
- **Scan errors are returned, not thrown.** Frappe rolls back a POST request on an exception, which would also erase the error's Scan Log. The API returns `{"ok": false, "message": ...}` so every failed scan stays in the audit trail.
- **Row lock while scanning.** `scan_pack` locks the Sales Order row (`for_update=True`), so two scanners cannot over-scan the same order at once.
- **Scanned serials win on the Delivery Note.** ERPNext auto-picks any active serial (FIFO) when a Delivery Note is saved. A `before_validate` hook fills in the scanned serials first, and `before_submit` blocks any serial that was not scanned for that order.
- **Least-privilege API user.** The API user has only the Sales User and Stock User roles, never Administrator. Every whitelisted method checks `frappe.has_permission`.

## Custom DocTypes

| DocType | Purpose |
|---|---|
| Pack Traceability | One record per pack serial (named by the serial): Stock Entry, Work Order, BMS serial, manufactured on |
| Pack Traceability Cell | Child table: cell serials inside the pack |
| Scan Log | Every scan, success or error, with user and time |

Custom field `Sales Order.external_order_id` ships as a fixture in `battery_track/fixtures/custom_field.json`.

## Setup

Requires Frappe and ERPNext v15, with a company already set up. The test scripts assume the company "ARB Accessories Pvt. Ltd" (abbreviation `AAPL`). To use another company, change `COMPANY`, `STORES` and `FINISHED_GOODS` in `battery_track/setup/test_data.py`.

```bash
cd ~/frappe-bench
bench get-app https://github.com/mayankahuja-pro/battery_track.git --branch develop
bench --site <site> install-app battery_track
bench --site <site> migrate
```

Then create the demo data in order:

```bash
S="bench --site <site> execute battery_track.setup"
$S.test_data.create                    # items, supplier, customer
$S.stock_in.create_purchase_receipt    # 20 cells, 2 BMS, 2 casings, with serials
$S.manufacture.create_bom
$S.manufacture.create_work_order
$S.manufacture.make_manufacture_entry --kwargs "{'work_order': '<work order name>'}"   # builds PACK-0001
$S.test_data.create_api_user           # prints api_key and api_secret
```

All scripts can be run again safely. They skip records that already exist.

> **Older sites:** if a site was installed with an older ERPNext 15 and you see `Unknown column 'tabContact.is_billing_contact'`, run
> `bench --site <site> execute erpnext.setup.install.create_address_and_contact_custom_fields`.
> That custom field is created only at install time, so `migrate` does not add it.

## API

Auth header: `Authorization: token <api_key>:<api_secret>`. Both methods accept POST only.

### Create an order

```bash
curl -X POST http://<site>:8000/api/method/battery_track.api.create_order \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"external_order_id": "SHARMA-PO-1001",
       "customer": "Sharma EV Dealers",
       "items": [{"item_code": "PACK-48V", "qty": 1}]}'
```

```json
{"message": {"ok": true, "created": true, "sales_order": "SAL-ORD-2026-00001",
             "message": "Sales Order SAL-ORD-2026-00001 created"}}
```

Sending the same `external_order_id` again returns the same Sales Order with `"created": false`.

### Scan a pack

```bash
curl -X POST http://<site>:8000/api/method/battery_track.api.scan_pack \
  -H "Authorization: token <api_key>:<api_secret>" \
  -H "Content-Type: application/json" \
  -d '{"sales_order": "SAL-ORD-2026-00001", "serial_no": "PACK-0001"}'
```

```json
{"message": {"ok": true, "message": "PACK-0001 OK (1/1 scanned for PACK-48V)"}}
```

The checks run in this order. The first one that fails is returned:

| # | Check | Example error |
|---|---|---|
| 0 | Sales Order exists, is submitted and open | `Sales Order X not found` |
| 1 | Serial exists | `Serial No PACK-9999 does not exist` |
| 2 | Its item is on the order | `Item CELL-32V is not in Sales Order ...` |
| 3 | In stock (Active, in a warehouse) | `Serial No CELL-0001 is not in stock (status: Consumed)` |
| 4 | Not already scanned | `... already scanned for Sales Order SAL-ORD-2026-00001` |
| 5 | Not more than ordered | `All 2 x CELL-32V already scanned for this order` |

## Battery Trace report

Open `/app/query-report/Battery Trace` (or search "Battery Trace" in the awesome bar) and filter by pack serial. It shows the pack's current status; the build details (Work Order, Stock Entry, date); the BMS and all 16 cell serials; and the Sales Order, customer, scan details and Delivery Note. Every value links to its document.

## Scanner app (Flutter)

`scanner_app/` is a small Flutter app for the warehouse: log in (site URL, API key and secret), enter a Sales Order, then scan pack barcodes with the camera (`mobile_scanner`) or type them in. A USB barcode gun works through the text box too. Each scan calls `scan_pack` and shows a large ✅ or ❌ with the server's message. All checks run on the server; the app only displays the result.

```bash
cd scanner_app
flutter pub get
flutter run -d chrome --web-port 5000
```

For the web build, allow the app's origin on the site:

```bash
bench --site <site> set-config allow_cors '["http://localhost:5000"]' --parse
```

`scanner_app/test_barcodes/index.html` has QR codes for testing (one valid pack and three error cases). The app also builds for Android. Its manifest already includes the INTERNET permission and allows cleartext HTTP for local testing.

## Screenshots

| | |
|---|---|
| Battery Trace for PACK-0001 | ![Battery Trace](docs/screenshots/battery_trace.png) |
| Pack Traceability record | ![Pack Traceability](docs/screenshots/pack_traceability.png) |
| Scan Log (success and errors) | ![Scan Log](docs/screenshots/scan_log.png) |
| Delivery Note blocked (pack not scanned) | ![Dispatch blocked](docs/screenshots/dispatch_blocked.png) |

## Project layout

```
battery_track/
├── api.py                       # create_order, scan_pack
├── hooks.py                     # doc_events + fixtures
├── events/
│   ├── stock_entry.py           # Manufacture -> Pack Traceability
│   └── delivery_note.py         # dispatch rule
├── battery_track/doctype/       # Pack Traceability, Pack Traceability Cell, Scan Log
├── battery_track/report/battery_trace/
├── fixtures/custom_field.json   # Sales Order.external_order_id
└── setup/                       # test data scripts (test_data, stock_in, manufacture)
scanner_app/                     # Flutter scanner (lib/api.dart + 3 screens)
```

## Known limitations

- A pack that comes back on a Sales Return becomes Active again, but its old successful Scan Log still blocks it from being scanned for a new order. The fix is to count only scans for orders that are not yet delivered.
- Cell and BMS item codes are constants in `events/stock_entry.py`. More pack models would need an Item field such as "Component Type".
- There is no "undo scan" yet. A wrong scan that succeeded has to be deleted by a System Manager.

## License

MIT
