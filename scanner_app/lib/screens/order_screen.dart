import 'package:flutter/material.dart';

import '../api.dart';
import 'login_screen.dart';
import 'scan_screen.dart';

class OrderScreen extends StatefulWidget {
  final ErpApi api;

  const OrderScreen({super.key, required this.api});

  @override
  State<OrderScreen> createState() => _OrderScreenState();
}

class _OrderScreenState extends State<OrderScreen> {
  final _order = TextEditingController(text: 'SAL-ORD-2026-');
  bool _loading = false;
  String? _error;

  Future<void> _open() async {
    final name = _order.text.trim().toUpperCase();
    setState(() {
      _loading = true;
      _error = null;
    });

    // check the order exists and show its customer, before starting to scan
    final result = await widget.api.getSalesOrder(name);
    if (!mounted) return;
    setState(() => _loading = false);

    if (!result.ok) {
      setState(() => _error = result.message);
      return;
    }
    if (result.data['docstatus'] != 1) {
      setState(() => _error = 'Sales Order $name is not submitted');
      return;
    }

    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => ScanScreen(api: widget.api, salesOrder: name, customer: result.message),
    ));
  }

  Future<void> _logout() async {
    await ErpApi.logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pick for Sales Order'),
        actions: [IconButton(onPressed: _logout, icon: const Icon(Icons.logout), tooltip: 'Logout')],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Connected to ${widget.api.baseUrl}', style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 16),
          TextField(
            controller: _order,
            decoration: const InputDecoration(labelText: 'Sales Order', border: OutlineInputBorder()),
            textCapitalization: TextCapitalization.characters,
            onSubmitted: (_) => _open(),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _loading ? null : _open,
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Start Scanning'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
        ],
      ),
    );
  }
}
