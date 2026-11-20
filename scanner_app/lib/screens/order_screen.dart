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
    if (name.isEmpty) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    // check the order exists and show its customer, before starting to scan
    final result = await widget.api.getSalesOrder(name);
    if (!mounted) return;
    setState(() => _loading = false);

    if (result.authError) {
      goToLogin(context, message: result.message);
      return;
    }
    if (!result.ok) {
      setState(() => _error = result.message);
      return;
    }
    if (result.data['docstatus'] != 1) {
      setState(() => _error = 'Sales Order $name is not submitted yet');
      return;
    }

    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => ScanScreen(api: widget.api, salesOrder: name, customer: result.message),
    ));
  }

  Future<void> _confirmLogout() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout?'),
        content: const Text('The saved API key and secret will be removed from this device.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Logout')),
        ],
      ),
    );
    if (yes == true && mounted) goToLogin(context);
  }

  @override
  void dispose() {
    _order.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pick for Sales Order'),
        actions: [IconButton(onPressed: _confirmLogout, icon: const Icon(Icons.logout), tooltip: 'Logout')],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: ListView(
            padding: const EdgeInsets.all(16),
            shrinkWrap: true,
            children: [
              Text('Connected to ${widget.api.baseUrl}', style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 16),
              TextField(
                controller: _order,
                decoration: const InputDecoration(labelText: 'Sales Order', border: OutlineInputBorder()),
                textCapitalization: TextCapitalization.characters,
                autocorrect: false,
                onSubmitted: (_) => _open(),
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: _loading ? null : _open,
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                icon: _loading
                    ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.qr_code_scanner),
                label: const Text('Start Scanning'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
