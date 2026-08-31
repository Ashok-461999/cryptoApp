import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../models/account.dart';
import '../models/crypto_signal.dart';

class ApiService {
  final String baseUrl;
  ApiService({String? baseUrl}) : baseUrl = baseUrl ?? AppConfig.apiBaseUrl;

  Future<ActiveSignalsResponse> fetchActiveSignals() async {
    final r = await http.get(Uri.parse('$baseUrl/signals/active'));
    if (r.statusCode != 200) throw Exception('Failed to load signals: ${r.statusCode}');
    return ActiveSignalsResponse.fromJson(jsonDecode(r.body) as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> fetchWatchlist() async {
    final r = await http.get(Uri.parse('$baseUrl/crypto/watchlist'));
    if (r.statusCode != 200) throw Exception('Failed to load watchlist');
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchHealth() async {
    final r = await http.get(Uri.parse('$baseUrl/health'));
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<AccountStats> fetchAccountStats() async {
    final r = await http.get(Uri.parse('$baseUrl/account/stats'));
    if (r.statusCode != 200) throw Exception('Failed to load account stats');
    return AccountStats.fromJson(jsonDecode(r.body) as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> fetchTradeHistory({int limit = 100}) async {
    final r = await http.get(Uri.parse('$baseUrl/signals/history?limit=$limit'));
    if (r.statusCode != 200) throw Exception('Failed to load history');
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchMemeCoins({bool refresh = false}) async {
    final r = await http.get(Uri.parse('$baseUrl/crypto/meme?refresh=$refresh'));
    if (r.statusCode != 200) throw Exception('Failed to load meme coins');
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> fetchCandles(String symbol, {String interval = '5m', int limit = 120}) async {
    final r = await http.get(Uri.parse('$baseUrl/crypto/candles?symbol=$symbol&interval=$interval&limit=$limit'));
    if (r.statusCode != 200) throw Exception('Failed to load candles');
    final body = jsonDecode(r.body) as Map<String, dynamic>;
    return (body['candles'] as List? ?? []).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> fetchMarkets({bool refresh = false}) async {
    final r = await http.get(Uri.parse('$baseUrl/crypto/markets'));
    if (r.statusCode != 200) throw Exception('Failed to load markets');
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchMarketNews({int limit = 50}) async {
    final r = await http.get(Uri.parse('$baseUrl/news/market?limit=$limit'));
    if (r.statusCode != 200) throw Exception('Failed to load news');
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchTradingSettings({String? clientId}) async {
    final q = clientId != null && clientId.isNotEmpty ? '?client_id=$clientId' : '';
    final r = await http.get(Uri.parse('$baseUrl/settings/trading$q'));
    if (r.statusCode != 200) throw Exception('Failed to load settings');
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> registerClient({String? clientId}) async {
    final r = await http.post(
      Uri.parse('$baseUrl/settings/client/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'client_id': clientId}),
    );
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> saveClientCredentials({
    required String clientId,
    String apiKey = '',
    String apiSecret = '',
    bool paperEnabled = true,
    bool liveAutoTrade = false,
  }) async {
    final r = await http.post(
      Uri.parse('$baseUrl/settings/client/credentials'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'client_id': clientId,
        'api_key': apiKey,
        'api_secret': apiSecret,
        'paper_enabled': paperEnabled,
        'live_auto_trade': liveAutoTrade,
      }),
    );
    final body = jsonDecode(r.body) as Map<String, dynamic>;
    if (r.statusCode != 200 || body['ok'] != true) {
      throw Exception(body['reason'] ?? 'Failed to save credentials');
    }
    return body;
  }

  Future<Map<String, dynamic>> resetPaperWallet(String clientId) async {
    final r = await http.post(
      Uri.parse('$baseUrl/settings/client/paper-reset'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'client_id': clientId}),
    );
    return jsonDecode(r.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> startTrading() async {
    final r = await http.post(Uri.parse('$baseUrl/settings/trading/start'));
    final body = jsonDecode(r.body) as Map<String, dynamic>;
    if (r.statusCode != 200) {
      throw Exception(body['detail'] ?? 'Failed to start trading');
    }
    return body;
  }

  Future<Map<String, dynamic>> stopTrading() async {
    final r = await http.post(Uri.parse('$baseUrl/settings/trading/stop'));
    final body = jsonDecode(r.body) as Map<String, dynamic>;
    if (r.statusCode != 200) {
      throw Exception(body['detail'] ?? 'Failed to stop trading');
    }
    return body;
  }

  Future<Map<String, dynamic>> takeSignal(Map<String, dynamic> payload) async {
    final r = await http.post(
      Uri.parse('$baseUrl/signals/take'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    final body = jsonDecode(r.body) as Map<String, dynamic>;
    if (r.statusCode != 200) {
      throw Exception(body['detail'] ?? 'Failed to take signal');
    }
    return body;
  }

  Future<Map<String, dynamic>> skipSignal({
    required String symbol,
    required String setup,
    required String direction,
  }) async {
    final r = await http.post(
      Uri.parse('$baseUrl/signals/skip'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'symbol': symbol, 'setup': setup, 'direction': direction}),
    );
    if (r.statusCode != 200) throw Exception('Failed to skip signal');
    return jsonDecode(r.body) as Map<String, dynamic>;
  }
}
