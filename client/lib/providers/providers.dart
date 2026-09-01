import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/account.dart';
import '../models/crypto_signal.dart';
import '../services/api_service.dart';
import '../services/client_credentials.dart';
import '../services/server_config.dart';

final clientIdProvider = FutureProvider<String>((ref) => ClientCredentialsStore.getOrCreateClientId());

final serverUrlProvider = FutureProvider<String>((ref) => ServerConfig.getBaseUrl());

final apiServiceProvider = Provider<ApiService>((ref) {
  final urlAsync = ref.watch(serverUrlProvider);
  final url = urlAsync.valueOrNull ?? 'http://127.0.0.1:8000';
  return ApiService(baseUrl: url);
});

final activeSignalsProvider = FutureProvider<ActiveSignalsResponse>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchActiveSignals();
});

final watchlistProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchWatchlist();
});

final healthProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchHealth();
});

final accountStatsProvider = FutureProvider<AccountStats>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchAccountStats();
});

final tradeHistoryProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchTradeHistory();
});

final memeCoinsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchMemeCoins();
});

final marketsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchMarkets(lightweight: false);
});

final marketsLightProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchMarkets(lightweight: true);
});

final marketNewsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  return ref.read(apiServiceProvider).fetchMarketNews();
});

final tradingSettingsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  ref.watch(serverUrlProvider);
  final clientId = await ref.watch(clientIdProvider.future);
  await ref.read(apiServiceProvider).registerClient(clientId: clientId);
  return ref.read(apiServiceProvider).fetchTradingSettings(clientId: clientId);
});
