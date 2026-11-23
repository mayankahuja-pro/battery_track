import 'package:flutter/material.dart';

import '../api.dart';
import 'order_screen.dart';

/// Clear the saved login and go back to the login screen (used when the server says 401).
Future<void> goToLogin(BuildContext context, {String? message}) async {
  await ErpApi.logout();
  if (!context.mounted) return;
  // remove every screen from the back stack, so "Back" can't return to a logged-out screen
  Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute(builder: (_) => LoginScreen(message: message)),
    (route) => false,
  );
}

class LoginScreen extends StatefulWidget {
  /// optional message to show on open, e.g. "Login expired"
  final String? message;

  const LoginScreen({super.key, this.message});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  // Server address is fixed when the app is BUILT, so warehouse staff never type it:
  //   flutter build apk --dart-define=ERP_URL=https://erp.arb.com
  // Without --dart-define we use the live Frappe Cloud site.
  static const _defaultUrl = String.fromEnvironment('ERP_URL', defaultValue: 'https://mayankahuja.frappe.cloud');

  final _url = TextEditingController(text: _defaultUrl);
  bool _editServer = false; // URL box stays hidden unless someone taps "Change"
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  bool _showPassword = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _error = widget.message;
  }

  Future<void> _login() async {
    // remove trailing "/" so we don't build URLs like "...8000//api"
    final url = _url.text.trim().replaceAll(RegExp(r'/+$'), '');
    final username = _username.text.trim();
    final password = _password.text; // no trim: spaces can be part of a password

    // check input before calling the server
    final urlError = ErpApi.checkUrl(url);
    if (urlError != null) {
      setState(() => _error = urlError);
      return;
    }
    if (username.isEmpty || password.isEmpty) {
      setState(() => _error = 'Enter username and password');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    // 1. server checks the password and gives back this user's API key + secret
    final result = await ErpApi.loginWithPassword(url, username, password);
    if (!mounted) return;

    if (!result.ok) {
      setState(() {
        _loading = false;
        _error = result.authError ? 'Wrong username or password' : result.message;
      });
      return;
    }

    // 2. from now on the app uses the token, and the password is not stored anywhere
    final api = ErpApi(url, result.data['api_key'], result.data['api_secret']);
    await api.save();
    _password.clear();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => OrderScreen(api: api)));
  }

  @override
  void dispose() {
    _url.dispose();
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Battery Scanner: Login')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480), // looks right on tablets / desktop browser too
          child: AutofillGroup(
            // lets the phone's password manager fill / save the login
            child: ListView(
              padding: const EdgeInsets.all(16),
              shrinkWrap: true,
              children: [
                const Icon(Icons.battery_charging_full, size: 64, color: Colors.green),
                const SizedBox(height: 16),
                TextField(
                  controller: _username,
                  decoration: const InputDecoration(
                    labelText: 'Username / Email',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.person),
                  ),
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  autofillHints: const [AutofillHints.username],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  obscureText: !_showPassword, // hidden by default
                  autocorrect: false,
                  enableSuggestions: false, // keyboard must not learn the password
                  autofillHints: const [AutofillHints.password],
                  decoration: InputDecoration(
                    labelText: 'Password',
                    border: const OutlineInputBorder(),
                    prefixIcon: const Icon(Icons.lock),
                    suffixIcon: IconButton(
                      icon: Icon(_showPassword ? Icons.visibility_off : Icons.visibility),
                      onPressed: () => setState(() => _showPassword = !_showPassword),
                    ),
                  ),
                  onSubmitted: (_) => _login(),
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: _loading ? null : _login,
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)), // big button for gloves
                  child: _loading
                      ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Login'),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 24),

                // Server: small and out of the way. The box opens only for setup / IT people.
                if (_editServer)
                  TextField(
                    controller: _url,
                    decoration: const InputDecoration(labelText: 'Server URL', border: OutlineInputBorder()),
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                  )
                else
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.dns, size: 16, color: Theme.of(context).hintColor),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(
                          _url.text,
                          style: TextStyle(color: Theme.of(context).hintColor),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      TextButton(onPressed: () => setState(() => _editServer = true), child: const Text('Change')),
                    ],
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
