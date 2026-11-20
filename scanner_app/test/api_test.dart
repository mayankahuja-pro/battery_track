import 'package:flutter_test/flutter_test.dart';

import 'package:battery_scanner/api.dart';

void main() {
  group('ErpApi.checkUrl (http only allowed on local network)', () {
    test('https is always fine', () {
      expect(ErpApi.checkUrl('https://erp.arb.com'), isNull);
    });
    test('http on local addresses is fine', () {
      expect(ErpApi.checkUrl('http://arb.localhost:8000'), isNull);
      expect(ErpApi.checkUrl('http://192.168.1.20:8000'), isNull);
      expect(ErpApi.checkUrl('http://172.28.156.165:8000'), isNull);
    });
    test('http on a public server is blocked', () {
      expect(ErpApi.checkUrl('http://erp.arb.com'), isNotNull);
      expect(ErpApi.checkUrl('http://172.32.0.1'), isNotNull); // outside 172.16-31 private range
    });
    test('garbage is rejected', () {
      expect(ErpApi.checkUrl('arb.localhost'), isNotNull); // no scheme
      expect(ErpApi.checkUrl('ftp://arb.localhost'), isNotNull);
    });
  });
}
