import 'package:flutter/material.dart';

import 'api.dart';
import 'screens/login_screen.dart';
import 'screens/order_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized(); // needed before using plugins in main()
  final api = await ErpApi.load(); // saved login, or null on first run
  runApp(BatteryScannerApp(api: api));
}

class BatteryScannerApp extends StatelessWidget {
  final ErpApi? api;

  const BatteryScannerApp({super.key, this.api});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Battery Scanner',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: Colors.green, useMaterial3: true),
      // already logged in -> go straight to the order screen
      home: api == null ? const LoginScreen() : OrderScreen(api: api!),
    );
  }
}
