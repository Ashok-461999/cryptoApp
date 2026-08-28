import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';

const _keyServerUrl = 'server_base_url';

/// Live AWS EC2 backend — auto-connected (no manual URL in Settings).
const String productionApiUrl = 'http://13.201.83.70';

/// Android emulator reaches PC via 10.0.2.2 (local dev only).
const String emulatorPcUrl = 'http://10.0.2.2:8000';

String get _defaultUrl {
  const devHost = String.fromEnvironment('DEV_HOST_URL', defaultValue: '');
  if (devHost.isNotEmpty) return devHost;
  return productionApiUrl;
}

class ServerConfig {
  static String? _cached;

  static Future<String> getBaseUrl() async {
    if (_cached != null) return _cached!;
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_keyServerUrl);
    if (saved == null || saved.isEmpty || _isLocalhost(saved)) {
      _cached = _defaultUrl;
      return _cached!;
    }
    _cached = saved;
    return _cached!;
  }

  static bool _isLocalhost(String url) =>
      url.contains('127.0.0.1') || url.contains('localhost');

  static Future<bool> needsSetup() async => false;

  static Future<String> ensureConfigured() async {
    final url = _defaultUrl;
    await setBaseUrl(url);
    return url;
  }

  static Future<void> setBaseUrl(String url) async {
    final clean = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyServerUrl, clean);
    _cached = clean;
  }

  static Future<void> clearCache() async {
    _cached = null;
  }
}
