import 'package:flutter_test/flutter_test.dart';

import 'package:battery_scanner/main.dart';

void main() {
  testWidgets('first run (no saved login) shows the login screen', (tester) async {
    await tester.pumpWidget(const BatteryScannerApp(api: null));

    expect(find.text('Battery Scanner: Login'), findsOneWidget);
    expect(find.text('Site URL'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
  });
}
