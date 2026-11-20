import 'package:flutter/material.dart';

import '../api.dart';
import 'order_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _url = TextEditingController(text: 'http://arb.localhost:8000');
  final _key = TextEditingController();
  final _secret = TextEditingController();
  bool _loading = false;
  String? _error;

  Future<void> _login() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    // remove trailing "/" so we don't build URLs like "...8000//api"
    final url = _url.text.trim().replaceAll(RegExp(r'/+$'), '');
    final api = ErpApi(url, _key.text.trim(), _secret.text.trim());

    final result = await api.testLogin(); // check before saving
    if (!mounted) return;

    if (result.ok) {
      await api.save();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => OrderScreen(api: api)),
      );
    } else {
      setState(() {
        _loading = false;
        _error = result.message;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Battery Scanner: Login')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _url,
            decoration: const InputDecoration(labelText: 'Site URL', border: OutlineInputBorder()),
            keyboardType: TextInputType.url,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _key,
            decoration: const InputDecoration(labelText: 'API Key', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _secret,
            obscureText: true, // hide the secret on screen
            decoration: const InputDecoration(labelText: 'API Secret', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _loading ? null : _login,
            child: _loading
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Login'),
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
