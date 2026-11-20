import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../api.dart';
import '../feedback.dart';
import 'login_screen.dart';

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
  final _manualFocus = FocusNode();
  final _feedback = ScanFeedback();
  final List<ScanEntry> _history = [];

  bool _busy = false; // true while one scan is being sent to the server
  ScanEntry? _last; // big ✅ / ❌ banner

  // progress from the server: [{item_code, item_name, ordered, scanned}]
  List<Map<String, dynamic>> _items = [];
  bool _complete = false;

  @override
  void initState() {
    super.initState();
    _loadProgress();
  }

  Future<void> _loadProgress() async {
    final result = await widget.api.getScanProgress(widget.salesOrder);
    if (!mounted) return;
    if (result.authError) return _logout(result.message);
    if (!result.ok) return; // progress is extra info; scanning still works without it

    setState(() {
      _items = List<Map<String, dynamic>>.from(result.data['items']);
      _complete = result.data['complete'] == true;
    });
  }

  // Camera found a barcode
  void _onDetect(BarcodeCapture capture) {
    final value = capture.barcodes.firstOrNull?.rawValue;
    if (value != null) _scan(value);
  }

  // Send one serial to ERPNext. The server does all the checks; the app only shows the answer.
  Future<void> _scan(String raw) async {
    final serial = raw.trim().toUpperCase();
    if (serial.isEmpty || _busy) return; // ignore while the previous scan is still running

    setState(() => _busy = true);
    final result = await widget.api.scanPack(widget.salesOrder, serial);
    if (!mounted) return;

    if (result.authError) return _logout(result.message);

    // sound + vibration first: the worker is looking at the pack, not the screen
    result.ok ? _feedback.success() : _feedback.error();

    final entry = ScanEntry(serial, result.ok, result.message);
    setState(() {
      _busy = false;
      _last = entry;
      _history.insert(0, entry); // newest on top
    });
    _manual.clear();
    _manualFocus.requestFocus(); // ready for the next USB-gun scan

    if (result.ok) _loadProgress(); // update "1/2 scanned"
  }

  void _logout(String message) => goToLogin(context, message: message);

  @override
  void dispose() {
    _camera.dispose(); // release the camera when leaving the screen
    _manual.dispose();
    _manualFocus.dispose();
    _feedback.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.salesOrder),
        actions: [
          // Torch button: shown only when the device has a flashlight
          ValueListenableBuilder(
            valueListenable: _camera,
            builder: (context, state, _) {
              if (state.torchState == TorchState.unavailable) return const SizedBox.shrink();
              final on = state.torchState == TorchState.on;
              return IconButton(
                tooltip: on ? 'Torch off' : 'Torch on',
                icon: Icon(on ? Icons.flash_on : Icons.flash_off),
                onPressed: _camera.toggleTorch,
              );
            },
          ),
          IconButton(tooltip: 'Refresh progress', icon: const Icon(Icons.refresh), onPressed: _loadProgress),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 600),
          child: Column(
            children: [
              _ProgressCard(customer: widget.customer, items: _items, complete: _complete),

              // Camera preview
              SizedBox(
                height: 220,
                child: MobileScanner(
                  controller: _camera,
                  onDetect: _onDetect,
                  errorBuilder: (context, error) => Container(
                    color: Colors.black12,
                    alignment: Alignment.center,
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      'Camera not available (${error.errorCode.name}).\nType or gun-scan the serial below.',
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
                  focusNode: _manualFocus,
                  autofocus: true,
                  autocorrect: false,
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
        ),
      ),
    );
  }
}

/// Customer + "PACK-48V  1 / 2" bars + green "Order complete" when everything is scanned.
class _ProgressCard extends StatelessWidget {
  final String customer;
  final List<Map<String, dynamic>> items;
  final bool complete;

  const _ProgressCard({required this.customer, required this.items, required this.complete});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(12),
      color: complete ? Colors.green.withValues(alpha: 0.15) : null,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.store),
                const SizedBox(width: 8),
                Expanded(child: Text(customer, style: const TextStyle(fontWeight: FontWeight.w600))),
                if (complete)
                  const Chip(avatar: Icon(Icons.check, color: Colors.green), label: Text('Order complete')),
              ],
            ),
            for (final item in items) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(child: Text('${item['item_name']} (${item['item_code']})')),
                  Text('${item['scanned']} / ${item['ordered']}', style: const TextStyle(fontWeight: FontWeight.bold)),
                ],
              ),
              const SizedBox(height: 4),
              LinearProgressIndicator(
                value: item['ordered'] == 0 ? 0 : item['scanned'] / item['ordered'],
                minHeight: 8,
                borderRadius: BorderRadius.circular(4),
              ),
            ],
          ],
        ),
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
    // fixed light colors + dark text: readable in both light and dark mode
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
            child: Text(
              entry.message,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.black87),
            ),
          ),
        ],
      ),
    );
  }
}
