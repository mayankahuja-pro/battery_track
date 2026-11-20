import 'package:flutter_test/flutter_test.dart';

import 'package:battery_scanner/main.dart';

void main() {
  testWidgets('first run (no saved login) shows the login screen', (tester) async {
    await tester.pumpWidget(const BatteryScannerApp(api: null));

    expect(find.text('Battery Scanner: Login'), findsOneWidget);
    expect(find.text('http://arb.localhost:8000'), findsOneWidget); // server shown as small text, not a box
    expect(find.text('Change'), findsOneWidget);
    expect(find.text('Username / Email'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
  });
}
