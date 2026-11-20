import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Result of one API call, in the same shape as our scan_pack response.
class ApiResult {
  final bool ok;
  final String message;
  final Map<String, dynamic> data;

  ApiResult(this.ok, this.message, [this.data = const {}]);
}

/// All calls to ERPNext live here, so the screens stay simple.
class ErpApi {
  final String baseUrl; // e.g. http://arb.localhost:8000
  final String apiKey;
  final String apiSecret;

  ErpApi(this.baseUrl, this.apiKey, this.apiSecret);

  // Frappe token auth: "token <api_key>:<api_secret>"
  Map<String, String> get _headers => {
        'Authorization': 'token $apiKey:$apiSecret',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      };

  Uri _url(String method, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl/api/method/$method').replace(queryParameters: query);

  /// Check that the URL + key + secret work. Returns the logged-in user.
  Future<ApiResult> testLogin() async {
    return _call(() => http.get(_url('frappe.auth.get_logged_user'), headers: _headers),
        (msg) => ApiResult(true, 'Logged in as $msg'));
  }

  /// Read a Sales Order's customer + status, so the user knows they typed the right one.
  Future<ApiResult> getSalesOrder(String name) async {
    final query = {
      'doctype': 'Sales Order',
      'filters': jsonEncode({'name': name}),
      'fieldname': jsonEncode(['customer', 'status', 'docstatus']),
    };
    return _call(() => http.get(_url('frappe.client.get_value', query), headers: _headers), (msg) {
      // Frappe returns {} (not null) when nothing matches
      if (msg == null || (msg as Map).isEmpty) return ApiResult(false, 'Sales Order $name not found');
      final data = Map<String, dynamic>.from(msg);
      return ApiResult(true, '${data['customer']} (${data['status']})', data);
    });
  }

  /// Our custom API: battery_track.api.scan_pack -> {"ok": true/false, "message": "..."}
  Future<ApiResult> scanPack(String salesOrder, String serialNo) async {
    final body = jsonEncode({'sales_order': salesOrder, 'serial_no': serialNo});
    return _call(
      () => http.post(_url('battery_track.api.scan_pack'), headers: _headers, body: body),
      (msg) => ApiResult(msg['ok'] == true, msg['message'].toString()),
    );
  }

  /// Common request handling: network errors, HTTP errors, Frappe error messages.
  Future<ApiResult> _call(
    Future<http.Response> Function() request,
    ApiResult Function(dynamic message) onSuccess,
  ) async {
    try {
      final res = await request().timeout(const Duration(seconds: 15));
      final json = res.body.isNotEmpty ? jsonDecode(res.body) : {};

      if (res.statusCode == 200) {
        return onSuccess(json['message']); // Frappe wraps the return value in "message"
      }
      if (res.statusCode == 401 || res.statusCode == 403) {
        return ApiResult(false, 'Not allowed (${res.statusCode}): check API key/secret and roles');
      }
      return ApiResult(false, _frappeError(json) ?? 'Server error ${res.statusCode}');
    } catch (e) {
      return ApiResult(false, 'Cannot reach server: $e');
    }
  }

  /// Frappe sends user-facing errors in "_server_messages" (a JSON string of JSON strings).
  String? _frappeError(dynamic json) {
    try {
      final list = jsonDecode(json['_server_messages']) as List;
      return jsonDecode(list.first)['message'].toString();
    } catch (_) {
      return json is Map ? json['exception']?.toString() : null;
    }
  }

  // ---- Saved settings (so the user logs in only once) ----
  // Note: shared_preferences is plain storage. For a real app use flutter_secure_storage for the secret.

  static Future<ErpApi?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final url = prefs.getString('url');
    final key = prefs.getString('key');
    final secret = prefs.getString('secret');
    if (url == null || key == null || secret == null) return null;
    return ErpApi(url, key, secret);
  }

  Future<void> save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('url', baseUrl);
    await prefs.setString('key', apiKey);
    await prefs.setString('secret', apiSecret);
  }

  static Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  }
}
