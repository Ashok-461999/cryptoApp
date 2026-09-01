import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/account.dart';
import '../models/market_prep.dart';
import '../models/crypto_signal.dart';
import '../services/notification_service.dart';
import '../services/server_config.dart';
import 'providers.dart';

class LiveSignalsState {
  final List<CryptoSignal> signals;
  final List<TradeRecord> recentClosed;
  final Map<String, double> prices;
  final int totalScanned;
  final int takeCountToday;
  final String takeCapLabel;
  final String utcDate;
  final bool connected;
  final String? error;
  final String? lastClosedMessage;
  final MarketPrep? marketPrep;

  const LiveSignalsState({
    this.signals = const [],
    this.recentClosed = const [],
    this.prices = const {},
    this.totalScanned = 0,
    this.takeCountToday = 0,
    this.takeCapLabel = 'unlimited',
    this.utcDate = '',
    this.connected = false,
    this.error,
    this.lastClosedMessage,
    this.marketPrep,
  });

  LiveSignalsState copyWith({
    List<CryptoSignal>? signals,
    List<TradeRecord>? recentClosed,
    Map<String, double>? prices,
    int? totalScanned,
    int? takeCountToday,
    String? takeCapLabel,
    String? utcDate,
    bool? connected,
    String? error,
    String? lastClosedMessage,
    MarketPrep? marketPrep,
  }) {
    return LiveSignalsState(
      signals: signals ?? this.signals,
      recentClosed: recentClosed ?? this.recentClosed,
      prices: prices ?? this.prices,
      totalScanned: totalScanned ?? this.totalScanned,
      takeCountToday: takeCountToday ?? this.takeCountToday,
      takeCapLabel: takeCapLabel ?? this.takeCapLabel,
      utcDate: utcDate ?? this.utcDate,
      connected: connected ?? this.connected,
      error: error,
      lastClosedMessage: lastClosedMessage,
      marketPrep: marketPrep ?? this.marketPrep,
    );
  }
}

class LiveSignalsNotifier extends StateNotifier<LiveSignalsState> {
  LiveSignalsNotifier(this._ref) : super(const LiveSignalsState()) {
    _init();
  }

  final Ref _ref;
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  String _baseUrl = 'http://127.0.0.1:8000';
  final Set<String> _notifiedKeys = {};

  Future<void> _init() async {
    _baseUrl = await ServerConfig.getBaseUrl();
    connect(_baseUrl);
  }

  void connect([String? baseUrl]) async {
    if (baseUrl != null) {
      _baseUrl = baseUrl;
    } else {
      _baseUrl = await ServerConfig.getBaseUrl();
    }
    _openSocket();
  }

  void _openSocket() {
    _channel?.sink.close();
    _reconnectTimer?.cancel();

    final wsBase = _baseUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');
    final uri = Uri.parse('$wsBase/ws/signals');

    try {
      _channel = WebSocketChannel.connect(uri);
      state = state.copyWith(connected: true, error: null);
      _channel!.stream.listen(
        _onMessage,
        onError: (e) {
          state = state.copyWith(connected: false, error: 'Cannot reach AWS server — retrying…');
          _scheduleReconnect();
        },
        onDone: () {
          state = state.copyWith(connected: false);
          _scheduleReconnect();
        },
      );
    } catch (e) {
      state = state.copyWith(connected: false, error: e.toString());
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), _openSocket);
  }

  void _onMessage(dynamic raw) {
    try {
      final msg = jsonDecode(raw as String) as Map<String, dynamic>;
      final type = msg['type'] as String? ?? '';
      final data = msg['data'] as Map<String, dynamic>? ?? {};

      if (type == 'snapshot') {
        _applySnapshot(data);
      } else if (type == 'price') {
        final sym = data['symbol'] as String? ?? '';
        final price = (data['price'] as num?)?.toDouble() ?? 0;
        if (sym.isNotEmpty && price > 0) {
          state = state.copyWith(prices: {...state.prices, sym: price});
        }
      } else if (type == 'trade_closed') {
        _handleTradeClosed(data);
      }
    } catch (_) {}
  }

  void _handleTradeClosed(Map<String, dynamic> data) {
    final trade = TradeRecord.fromJson(data);
    final reason = trade.closeReason ?? trade.status;
    final pnl = trade.pnlInr;
    final sign = pnl >= 0 ? '+' : '';
    final updated = [trade, ...state.recentClosed.where((t) => t.id != trade.id)].take(10).toList();

    state = state.copyWith(
      recentClosed: updated,
      lastClosedMessage: '${trade.symbol} $reason · $sign₹${pnl.toStringAsFixed(0)}',
    );
    _ref.invalidate(tradeHistoryProvider);
    _ref.invalidate(accountStatsProvider);
  }

  void _applySnapshot(Map<String, dynamic> data) {
    final list = (data['signals'] as List? ?? [])
        .map((e) => CryptoSignal.fromJson(e as Map<String, dynamic>))
        .toList();
    final pricesRaw = data['prices'] as Map<String, dynamic>? ?? {};
    final prices = pricesRaw.map((k, v) => MapEntry(k, (v as num).toDouble()));
    final closed = (data['recent_closed'] as List? ?? [])
        .map((e) => TradeRecord.fromJson(e as Map<String, dynamic>))
        .toList();

    for (final sig in list) {
      final isBest = sig.isHighPriority || sig.notify || sig.signalGrade == 'A+';
      if (!isBest) continue;
      final key = '${sig.symbol}:${sig.setup}:${sig.tradeId ?? sig.timestamp}';
      if (_notifiedKeys.contains(key)) continue;
      _notifiedKeys.add(key);
      NotificationService().showTakeSignal(
        symbol: sig.symbol,
        direction: sig.direction,
        setup: sig.setupLabel,
        confidence: sig.confidence,
        entry: sig.entryPrice,
        sl: sig.stopLossPrice,
        target: sig.target1Price,
        riskReward: sig.riskReward,
        riskInr: sig.riskPerTradeInr > 0 ? sig.riskPerTradeInr : sig.maxLossInr,
        targetInr: sig.targetPnlInr,
        grade: sig.signalGrade,
      );
    }

    final prepRaw = data['market_prep'] as Map<String, dynamic>?;
    final marketPrep = prepRaw != null ? MarketPrep.fromJson(prepRaw) : null;

    state = state.copyWith(
      signals: list,
      recentClosed: closed,
      prices: {...state.prices, ...prices},
      totalScanned: data['total_scanned'] as int? ?? 0,
      takeCountToday: data['take_count_today'] as int? ?? 0,
      takeCapLabel: '${data['take_cap_today'] ?? 'unlimited'}',
      utcDate: data['utc_date'] as String? ?? '',
      connected: true,
      error: null,
      marketPrep: marketPrep,
    );
  }

  Future<bool> takeSignal(CryptoSignal signal) async {
    try {
      final api = _ref.read(apiServiceProvider);
      final result = await api.takeSignal(signal.toTakePayload());
      final tradeId = (result['trade_id'] as num?)?.toInt();
      state = state.copyWith(
        takeCountToday: state.takeCountToday + 1,
        signals: state.signals
            .map((s) => s.symbol == signal.symbol && s.setup == signal.setup
                ? s.copyWith(tradeId: tradeId, status: 'TAKEN', userTaken: true)
                : s)
            .toList(),
      );
      _ref.invalidate(tradeHistoryProvider);
      _ref.invalidate(accountStatsProvider);
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  Future<void> skipSignal(CryptoSignal signal) async {
    try {
      final api = _ref.read(apiServiceProvider);
      await api.skipSignal(symbol: signal.symbol, setup: signal.setup, direction: signal.direction);
      state = state.copyWith(
        signals: state.signals.where((s) => !(s.symbol == signal.symbol && s.setup == signal.setup)).toList(),
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    super.dispose();
  }
}

final liveSignalsProvider =
    StateNotifierProvider<LiveSignalsNotifier, LiveSignalsState>((ref) {
  final notifier = LiveSignalsNotifier(ref);
  ref.onDispose(() => notifier.dispose());
  return notifier;
});
