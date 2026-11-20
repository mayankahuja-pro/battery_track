import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

/// Result of one API call.
class ApiResult {
  final bool ok;
  final String message;
  final Map<String, dynamic> data;

  /// true when the server rejected our API key/secret (HTTP 401) -> app must log out
  final bool authError;

  ApiResult(this.ok, this.message, {this.data = const {}, this.authError = false});
}

/// All calls to ERPNext live here, so the screens stay simple.
class ErpApi {
  final String baseUrl; // e.g. https://erp.arb.com or http://arb.localhost:8000
  final String apiKey;
  final String apiSecret;

  ErpApi(this.baseUrl, this.apiKey, this.apiSecret);

  // Encrypted storage: Android Keystore / iOS Keychain (on web: encrypted browser storage)
  static const _storage = FlutterSecureStorage();

  // Frappe token auth: "token <api_key>:<api_secret>"
  Map<String, String> get _headers => {
        'Authorization': 'token $apiKey:$apiSecret',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Uri _url(String method, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl/api/method/$method').replace(queryParameters: query);

  // ---------------------------------------------------------------------------
  // Login with username + password
  // ---------------------------------------------------------------------------

  /// Sends ID + password to our battery_track.api.app_login.
  /// On success, result.data has "api_key", "api_secret" and "full_name"; the screen saves them.
  /// No Authorization header here: we are not logged in yet.
  /// No retry: every try counts toward the server's limit of 5 logins per minute.
  static Future<ApiResult> loginWithPassword(String baseUrl, String username, String password) {
    final helper = ErpApi(baseUrl, '', ''); // only used to reach _send
    return helper._send(
      () => http.post(
        Uri.parse('$baseUrl/api/method/battery_track.api.app_login'),
        headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        body: jsonEncode({'usr': username, 'pwd': password}),
      ),
      (msg) => ApiResult(true, 'Welcome ${msg['full_name']}', data: Map<String, dynamic>.from(msg)),
    );
  }

  // ---------------------------------------------------------------------------
  // API calls
  // ---------------------------------------------------------------------------

  /// Check that URL + key + secret work. Returns the logged-in user.
  Future<ApiResult> testLogin() {
    return _send(
      () => http.get(_url('frappe.auth.get_logged_user'), headers: _headers),
      (msg) => ApiResult(true, 'Logged in as $msg'),
      retry: true,
    );
  }

  /// Read a Sales Order's customer + status, so the user knows they typed the right one.
  Future<ApiResult> getSalesOrder(String name) {
    final query = {
      'doctype': 'Sales Order',
      'filters': jsonEncode({'name': name}),
      'fieldname': jsonEncode(['customer', 'status', 'docstatus']),
    };
    return _send(
      () => http.get(_url('frappe.client.get_value', query), headers: _headers),
      (msg) {
        // Frappe returns {} (not null) when nothing matches
        if (msg == null || (msg as Map).isEmpty) return ApiResult(false, 'Sales Order $name not found');
        final data = Map<String, dynamic>.from(msg);
        return ApiResult(true, '${data['customer']} (${data['status']})', data: data);
      },
      retry: true,
    );
  }

  /// Ordered vs scanned per item -> {"items": [...], "complete": true/false}
  Future<ApiResult> getScanProgress(String salesOrder) {
    return _send(
      () => http.get(_url('battery_track.api.get_scan_progress', {'sales_order': salesOrder}),
          headers: _headers),
      (msg) => ApiResult(true, '', data: Map<String, dynamic>.from(msg)),
      retry: true,
    );
  }

  /// Our custom API: battery_track.api.scan_pack -> {"ok": true/false, "message": "..."}
  ///
  /// NO automatic retry here. If the first request reached the server but the reply was lost,
  /// a retry would answer "already scanned for this order" and show a false ❌.
  Future<ApiResult> scanPack(String salesOrder, String serialNo) {
    final body = jsonEncode({'sales_order': salesOrder, 'serial_no': serialNo});
    return _send(
      () => http.post(_url('battery_track.api.scan_pack'), headers: _headers, body: body),
      (msg) => ApiResult(msg['ok'] == true, msg['message'].toString()),
      networkErrorMessage: 'No reply from server, result unknown. Scan again: '
          '"already scanned for this order" means the first scan worked.',
    );
  }

  // ---------------------------------------------------------------------------
  // Common request handling
  // ---------------------------------------------------------------------------

  /// Sends the request and turns every outcome (success, HTTP error, no network) into an ApiResult.
  /// retry: try once more after a network failure. Only for read-only (GET) calls.
  Future<ApiResult> _send(
    Future<http.Response> Function() request,
    ApiResult Function(dynamic message) onSuccess, {
    bool retry = false,
    String? networkErrorMessage,
  }) async {
    final attempts = retry ? 2 : 1;

    for (var attempt = 1; attempt <= attempts; attempt++) {
      try {
        final res = await request().timeout(const Duration(seconds: 15));
        return _handleResponse(res, onSuccess);
      } on TimeoutException {
        if (attempt == attempts) return ApiResult(false, networkErrorMessage ?? 'Server is not responding. Try again.');
      } on http.ClientException {
        if (attempt == attempts) {
          return ApiResult(false, networkErrorMessage ?? 'Cannot reach server. Check Wi-Fi and the site URL.');
        }
      }
      await Future.delayed(const Duration(seconds: 1)); // small pause before the retry
    }
    return ApiResult(false, 'Unknown error'); // never reached, keeps Dart happy
  }

  ApiResult _handleResponse(http.Response res, ApiResult Function(dynamic message) onSuccess) {
    dynamic json;
    try {
      json = res.body.isNotEmpty ? jsonDecode(res.body) : {};
    } on FormatException {
      // got HTML instead of JSON: usually a wrong URL or a proxy error page
      return ApiResult(false, 'Unexpected reply from server (${res.statusCode}). Check the site URL.');
    }

    if (res.statusCode == 200) {
      return onSuccess(json['message']); // Frappe wraps the return value in "message"
    }
    if (res.statusCode == 401) {
      // key/secret wrong, or regenerated in ERPNext -> log out
      return ApiResult(false, 'Login expired or API key changed. Please log in again.', authError: true);
    }
    if (res.statusCode == 429) {
      // server's rate limit on login (5 tries per minute)
      return ApiResult(false, 'Too many attempts. Wait 1 minute and try again.');
    }
    if (res.statusCode == 403) {
      // key is valid but this user lacks the role (e.g. Stock User)
      return ApiResult(false, _frappeError(json) ?? 'Not allowed: your user lacks the required role.');
    }
    return ApiResult(false, _frappeError(json) ?? 'Server error ${res.statusCode}');
  }

  /// Frappe sends user-facing errors in "_server_messages" (a JSON string of JSON strings).
  String? _frappeError(dynamic json) {
    try {
      final list = jsonDecode(json['_server_messages']) as List;
      final message = jsonDecode(list.first)['message'].toString();
      return message.replaceAll(RegExp(r'<[^>]*>'), ''); // strip HTML tags like <b>
    } catch (_) {
      return json is Map ? json['exc_type']?.toString() : null;
    }
  }

  // ---------------------------------------------------------------------------
  // URL safety check
  // ---------------------------------------------------------------------------

  /// Returns an error message, or null if the URL is OK.
  /// http:// sends the API secret as plain text, so we allow it only on local / office-LAN addresses.
  static String? checkUrl(String url) {
    final uri = Uri.tryParse(url);
    if (uri == null || uri.host.isEmpty || !(uri.scheme == 'http' || uri.scheme == 'https')) {
      return 'Enter a full URL, e.g. https://erp.yourcompany.com';
    }
    if (uri.scheme == 'https') return null;

    final host = uri.host;
    final isLocal = host == 'localhost' ||
        host.endsWith('.localhost') ||
        host == '127.0.0.1' ||
        host.startsWith('10.') ||
        host.startsWith('192.168.') ||
        RegExp(r'^172\.(1[6-9]|2\d|3[01])\.').hasMatch(host);
    return isLocal ? null : 'Use https:// for a live server (http sends your API secret unencrypted).';
  }

  // ---------------------------------------------------------------------------
  // Saved login
  // ---------------------------------------------------------------------------

  static Future<ErpApi?> load() async {
    final url = await _storage.read(key: 'url');
    final key = await _storage.read(key: 'key');
    final secret = await _storage.read(key: 'secret');
    if (url == null || key == null || secret == null) return null;
    return ErpApi(url, key, secret);
  }

  Future<void> save() async {
    await _storage.write(key: 'url', value: baseUrl);
    await _storage.write(key: 'key', value: apiKey);
    await _storage.write(key: 'secret', value: apiSecret);
  }

  static Future<void> logout() => _storage.deleteAll();
}
