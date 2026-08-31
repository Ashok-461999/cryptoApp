import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

/// Stable device id + optional Binance keys (keys stored locally until sent to server).
class ClientCredentialsStore {
  static const _clientIdKey = 'scalptrack_client_id';
  static const _apiKeyKey = 'binance_api_key';
  static const _apiSecretKey = 'binance_api_secret';
  static const _paperEnabledKey = 'paper_enabled';
  static const _liveAutoKey = 'live_auto_trade';

  static Future<String> getOrCreateClientId() async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString(_clientIdKey);
    if (id != null && id.isNotEmpty) return id;
    id = _uuid();
    await prefs.setString(_clientIdKey, id);
    return id;
  }

  static String _uuid() {
    final r = Random.secure();
    final bytes = List<int>.generate(16, (_) => r.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  static Future<void> saveLocal({
    String? apiKey,
    String? apiSecret,
    bool? paperEnabled,
    bool? liveAutoTrade,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    if (apiKey != null) await prefs.setString(_apiKeyKey, apiKey);
    if (apiSecret != null) await prefs.setString(_apiSecretKey, apiSecret);
    if (paperEnabled != null) await prefs.setBool(_paperEnabledKey, paperEnabled);
    if (liveAutoTrade != null) await prefs.setBool(_liveAutoKey, liveAutoTrade);
  }

  static Future<Map<String, dynamic>> loadLocal() async {
    final prefs = await SharedPreferences.getInstance();
    return {
      'client_id': prefs.getString(_clientIdKey) ?? '',
      'api_key': prefs.getString(_apiKeyKey) ?? '',
      'api_secret': prefs.getString(_apiSecretKey) ?? '',
      'paper_enabled': prefs.getBool(_paperEnabledKey) ?? true,
      'live_auto_trade': prefs.getBool(_liveAutoKey) ?? false,
    };
  }
}
