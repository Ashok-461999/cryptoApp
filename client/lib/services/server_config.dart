import 'package:shared_preferences/shared_preferences.dart';

import '../config.dart';

const _keyServerUrl = 'server_base_url';

/// Phone on WiFi — change in Settings if your ipconfig shows different.
const String suggestedPcUrl = 'http://192.168.0.2:8000';

/// Android emulator reaches PC via 10.0.2.2 (host machine).
const String emulatorPcUrl = 'http://10.0.2.2:8000';

String get _setupUrl {
  const devHost = String.fromEnvironment('DEV_HOST_URL', defaultValue: '');
  if (devHost.isNotEmpty) return devHost;
  return suggestedPcUrl;
}

class ServerConfig {
  static String? _cached;

  static Future<String> getBaseUrl() async {
    if (_cached != null) return _cached!;
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_keyServerUrl) ?? AppConfig.apiBaseUrl;
    _cached = _isLocalhost(saved) ? _setupUrl : saved;
    return _cached!;
  }

  static bool _isLocalhost(String url) =>
      url.contains('127.0.0.1') || url.contains('localhost');

  static Future<bool> needsSetup() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_keyServerUrl);
    if (saved == null || saved.isEmpty) return true;
    return saved.contains('127.0.0.1') || saved.contains('localhost');
  }

  /// First launch: save PC URL so phone does not use 127.0.0.1 (phone itself).
  static Future<String> ensureConfigured() async {
    if (await needsSetup()) {
      await setBaseUrl(_setupUrl);
      return _setupUrl;
    }
    return getBaseUrl();
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
