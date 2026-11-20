import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../api.dart';

/// One line in the "recent scans" list.
class ScanEntry {
  final String serial;
  final bool ok;
  final String message;

  ScanEntry(this.serial, this.ok, this.message);
}

class ScanScreen extends StatefulWidget {
  final ErpApi api;
  final String salesOrder;
  final String customer;

  const ScanScreen({super.key, required this.api, required this.salesOrder, required this.customer});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  // noDuplicates: the camera reports the same barcode only once while it stays in view
  final _camera = MobileScannerController(detectionSpeed: DetectionSpeed.noDuplicates);
  final _manual = TextEditingController();
  final List<ScanEntry> _history = [];

  bool _busy = false; // true while one scan is being sent to the server
  ScanEntry? _last; // big ✅ / ❌ banner

  // Camera found a barcode
  void _onDetect(BarcodeCapture capture) {
    final value = capture.barcodes.firstOrNull?.rawValue;
    if (value != null) _scan(value);
  }

  // Send one serial to ERPNext. The server does all the checks; the app only shows the answer.
  Future<void> _scan(String raw) async {
    final serial = raw.trim();
    if (serial.isEmpty || _busy) return; // ignore while the previous scan is still running

    setState(() => _busy = true);
    final result = await widget.api.scanPack(widget.salesOrder, serial);
    if (!mounted) return;

    final entry = ScanEntry(serial, result.ok, result.message);
    setState(() {
      _busy = false;
      _last = entry;
      _history.insert(0, entry); // newest on top
    });
    _manual.clear();
  }

  @override
  void dispose() {
    _camera.dispose(); // release the camera when leaving the screen
    _manual.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final okCount = _history.where((e) => e.ok).length;

    return Scaffold(
      appBar: AppBar(title: Text(widget.salesOrder)),
      body: Column(
        children: [
          ListTile(
            leading: const Icon(Icons.store),
            title: Text(widget.customer),
            trailing: Chip(label: Text('$okCount scanned')),
          ),

          // Camera preview
          SizedBox(
            height: 240,
            child: MobileScanner(
              controller: _camera,
              onDetect: _onDetect,
              errorBuilder: (context, error) => Container(
                color: Colors.black12,
                alignment: Alignment.center,
                padding: const EdgeInsets.all(16),
                child: Text(
                  'Camera not available (${error.errorCode.name}).\nType the serial below instead.',
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ),

          // Manual entry: works without a camera and with USB barcode guns (they "type" + Enter)
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _manual,
              autofocus: true,
              textCapitalization: TextCapitalization.characters,
              decoration: InputDecoration(
                labelText: 'Serial No (type or scan)',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(icon: const Icon(Icons.send), onPressed: () => _scan(_manual.text)),
              ),
              onSubmitted: _scan,
            ),
          ),

          if (_busy) const LinearProgressIndicator(),
          if (_last != null) _ResultBanner(entry: _last!),

          // History of this session
          Expanded(
            child: ListView.builder(
              itemCount: _history.length,
              itemBuilder: (context, i) {
                final e = _history[i];
                return ListTile(
                  dense: true,
                  leading: Icon(e.ok ? Icons.check_circle : Icons.cancel, color: e.ok ? Colors.green : Colors.red),
                  title: Text(e.serial),
                  subtitle: Text(e.message),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// Big green / red banner for the latest scan, readable from a distance.
class _ResultBanner extends StatelessWidget {
  final ScanEntry entry;

  const _ResultBanner({required this.entry});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(horizontal: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: entry.ok ? Colors.green.shade100 : Colors.red.shade100,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Text(entry.ok ? '✅' : '❌', style: const TextStyle(fontSize: 32)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(entry.message, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}
