import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/crypto_signal.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';
import '../widgets/trading_chart.dart';

/// Full trading chart screen — tap any signal to see entry reason + chart.
class SignalChartScreen extends ConsumerStatefulWidget {
  final CryptoSignal? signal;
  final String symbol;
  final String? direction;
  final String? setup;
  final double? entry;
  final double? stopLoss;
  final double? target;
  final List<String> validityPoints;
  final String? decisionReason;
  final Map<String, dynamic>? chartLevels;
  final Map<String, dynamic>? newsContext;
  final String? strategyLabel;
  final String? chartNote;
  final String? prediction;

  const SignalChartScreen({
    super.key,
    this.signal,
    required this.symbol,
    this.direction,
    this.setup,
    this.entry,
    this.stopLoss,
    this.target,
    this.validityPoints = const [],
    this.decisionReason,
    this.chartLevels,
    this.newsContext,
    this.strategyLabel,
    this.chartNote,
    this.prediction,
  });

  factory SignalChartScreen.fromSignal(CryptoSignal s) => SignalChartScreen(
        signal: s,
        symbol: s.symbol,
        direction: s.direction,
        setup: s.setup,
        entry: s.entryPrice,
        stopLoss: s.stopLossPrice,
        target: s.target1Price,
        validityPoints: s.validityPoints,
        decisionReason: s.decisionReason,
      );

  @override
  ConsumerState<SignalChartScreen> createState() => _SignalChartScreenState();
}

class _SignalChartScreenState extends ConsumerState<SignalChartScreen> {
  String _interval = '5m';
  List<Map<String, dynamic>> _candles = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final c = await api.fetchCandles(widget.symbol, interval: _interval, limit: 150);
      if (mounted) setState(() => _candles = c);
    } catch (_) {
      if (mounted) setState(() => _candles = []);
    }
    if (mounted) setState(() => _loading = false);
  }

  String _formatPrice(double p) {
    if (p >= 1000) return NumberFormat('#,##0.00').format(p);
    if (p >= 1) return p.toStringAsFixed(4);
    return p.toStringAsFixed(8);
  }

  String get _setupLabel {
    if (widget.signal != null) return widget.signal!.setupLabel;
    return (widget.setup ?? '').replaceAll('_', ' ');
  }

  @override
  Widget build(BuildContext context) {
    final isLong = (widget.direction ?? 'LONG') == 'LONG';
    final dirColor = isLong ? AppColors.profit : AppColors.loss;
    final chart = widget.chartLevels;
    double? d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v');
    final support = d(chart?['support']);
    final resistance = d(chart?['resistance']);
    final strategyLine = d(chart?['strategy_line']);
    final expLow = d(chart?['expected_move_low']);
    final expHigh = d(chart?['expected_move_high']);
    final prediction = widget.prediction ?? chart?['prediction'] as String?;
    final news = widget.newsContext;

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        backgroundColor: AppColors.card,
        title: Text(widget.symbol, style: const TextStyle(fontWeight: FontWeight.w800)),
        actions: [
          if (widget.direction != null)
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(color: dirColor.withValues(alpha: 0.2), borderRadius: BorderRadius.circular(8)),
                  child: Text(widget.direction!, style: TextStyle(color: dirColor, fontWeight: FontWeight.w800, fontSize: 12)),
                ),
              ),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ChartTimeframeBar(
            selected: _interval,
            onSelected: (iv) {
              setState(() => _interval = iv);
              _load();
            },
          ),
          const SizedBox(height: 12),
          PremiumCard(
            padding: const EdgeInsets.all(12),
            child: TradingChart(
              candles: _candles,
              entry: widget.entry,
              stopLoss: widget.stopLoss,
              target: widget.target,
              support: support,
              resistance: resistance,
              strategyLine: strategyLine,
              expectedMoveLow: expLow,
              expectedMoveHigh: expHigh,
              prediction: prediction,
              interval: _interval,
              loading: _loading,
            ),
          ),
          if (widget.strategyLabel != null || widget.chartNote != null || news != null) ...[
            const SizedBox(height: 14),
            PremiumCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('STRATEGY & EXPECTED MOVE', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.gold, letterSpacing: 1)),
                  const SizedBox(height: 10),
                  if (widget.strategyLabel != null)
                    Text('Strategy: ${widget.strategyLabel}', style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.accentBlue)),
                  if (widget.chartNote != null && widget.chartNote!.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(widget.chartNote!, style: const TextStyle(fontSize: 12, color: AppColors.textMuted, height: 1.4)),
                  ],
                  if (support != null && support > 0) _LevelRow('Support', _formatPrice(support), AppColors.profit),
                  if (resistance != null && resistance > 0) _LevelRow('Resistance', _formatPrice(resistance), AppColors.loss),
                  if (strategyLine != null && strategyLine > 0) _LevelRow('Strategy line', _formatPrice(strategyLine), AppColors.accentBlue),
                  if (expLow != null && expHigh != null && expLow > 0 && expHigh > 0)
                    _LevelRow('Expected move', '${_formatPrice(expLow)} – ${_formatPrice(expHigh)}', AppColors.gold),
                ],
              ),
            ),
          ],
          if (news != null && (news['headline'] as String? ?? '').isNotEmpty) ...[
            const SizedBox(height: 12),
            PremiumCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('NEWS BIAS', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1)),
                  const SizedBox(height: 8),
                  Text(news['headline'] as String? ?? '', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.text)),
                  const SizedBox(height: 6),
                  Text(
                    news['note'] as String? ?? '',
                    style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.35),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 14),
          PremiumCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const           Text('WHY WE TOOK THIS ENTRY', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1)),
                const SizedBox(height: 10),
                if (widget.signal != null && widget.signal!.timestamp.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      'Signal given: ${widget.signal!.signalTimeLabel}',
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.accentBlue),
                    ),
                  ),
                Text('Setup: $_setupLabel', style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.text)),
                if (widget.decisionReason != null && widget.decisionReason!.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(widget.decisionReason!, style: const TextStyle(fontSize: 12, color: AppColors.textMuted, height: 1.4)),
                ],
                const SizedBox(height: 12),
                if (widget.entry != null) _LevelRow('Entry', _formatPrice(widget.entry!), AppColors.accent),
                if (widget.stopLoss != null) _LevelRow('Stop Loss', _formatPrice(widget.stopLoss!), AppColors.loss),
                if (widget.target != null) _LevelRow('Target 1', _formatPrice(widget.target!), AppColors.profit),
              ],
            ),
          ),
          if (widget.validityPoints.isNotEmpty) ...[
            const SizedBox(height: 12),
            PremiumCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('VALIDITY CHECKLIST', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.accentBlue, letterSpacing: 1)),
                  const SizedBox(height: 10),
                  ...widget.validityPoints.map((p) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Icon(Icons.check_circle_outline, size: 14, color: AppColors.profit),
                            const SizedBox(width: 8),
                            Expanded(child: Text(p, style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.35))),
                          ],
                        ),
                      )),
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _LevelRow extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _LevelRow(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 8),
          Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
          const Spacer(),
          Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: color)),
        ],
      ),
    );
  }
}

/// Open chart for a symbol (from markets) with optional signal lines.
void openSymbolChart(
  BuildContext context,
  String symbol, {
  Map<String, dynamic>? signal,
  Map<String, dynamic>? tracker,
  List<String> validityPoints = const [],
}) {
  double? d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v');
  final chart = (tracker?['chart'] as Map<String, dynamic>?) ??
      (tracker?['levels'] as Map<String, dynamic>?);
  final news = tracker?['news_context'] as Map<String, dynamic>?;
  Navigator.of(context).push(
    MaterialPageRoute(
      builder: (_) => SignalChartScreen(
        symbol: symbol,
        direction: signal?['direction'] as String? ??
            (tracker?['action'] == 'BUY'
                ? 'LONG'
                : tracker?['action'] == 'SELL'
                    ? 'SHORT'
                    : null),
        setup: signal?['setup'] as String? ?? tracker?['strategy'] as String?,
        entry: d(signal?['entry_price']) ?? d(tracker?['entry_price']) ?? d(chart?['strategy_line']),
        stopLoss: d(signal?['stop_loss_price']) ?? d(tracker?['stop_loss_price']) ?? d(chart?['stop_loss']),
        target: d(signal?['target_1_price']) ?? d(tracker?['target_1_price']) ?? d(chart?['target']),
        validityPoints: validityPoints,
        decisionReason: signal?['decision_reason'] as String? ?? tracker?['suggestion'] as String?,
        chartLevels: chart,
        newsContext: news,
        strategyLabel: tracker?['strategy_label'] as String?,
        chartNote: chart?['note'] as String?,
        prediction: chart?['prediction'] as String? ?? tracker?['prediction'] as String?,
      ),
    ),
  );
}

void openSignalChart(BuildContext context, CryptoSignal signal) {
  Navigator.of(context).push(
    MaterialPageRoute(builder: (_) => SignalChartScreen.fromSignal(signal)),
  );
}
