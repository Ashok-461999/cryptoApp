import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/live_signals_provider.dart';
import '../providers/providers.dart';
import '../screens/signal_chart_screen.dart';
import '../theme/app_theme.dart';
import '../utils/price_format.dart';
import '../widgets/alpha_markets_panel.dart';
import '../widgets/btc_gold_tracker.dart';
import '../widgets/trading_chart.dart';

class WatchlistScreen extends ConsumerStatefulWidget {
  const WatchlistScreen({super.key});

  @override
  ConsumerState<WatchlistScreen> createState() => _WatchlistScreenState();
}

class _WatchlistScreenState extends ConsumerState<WatchlistScreen> {
  Timer? _timer;
  bool _fullMarkets = false;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 90), (_) {
      if (_fullMarkets) ref.invalidate(marketsProvider);
    });
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() => _fullMarkets = true);
        ref.invalidate(marketsProvider);
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  String _formatPrice(double p) => formatPrice(p);

  @override
  Widget build(BuildContext context) {
    final live = ref.watch(liveSignalsProvider);
    final data = ref.watch(_fullMarkets ? marketsProvider : marketsLightProvider);

    return RefreshIndicator(
      color: AppColors.accent,
      onRefresh: () async {
        ref.invalidate(_fullMarkets ? marketsProvider : marketsLightProvider);
        await ref.read((_fullMarkets ? marketsProvider : marketsLightProvider).future);
      },
      child: data.when(
        data: (d) {
          final focus = (d['focus'] as List? ?? d['highlights'] as List? ?? [])
              .cast<Map<String, dynamic>>()
              .where((h) => h['is_focus'] == true || h['base'] == 'BTC' || h['base'] == 'GOLD')
              .toList();
          final focusTracker = (_fullMarkets
                  ? (d['focus_tracker'] as List? ?? live.focusTracker)
                  : live.focusTracker)
              .cast<Map<String, dynamic>>();
          final highlights = (d['highlights'] as List? ?? []).cast<Map<String, dynamic>>();
          final coins = (d['coins'] as List? ?? []).cast<Map<String, dynamic>>();
          final sentiment = d['sentiment'] as Map<String, dynamic>? ?? {};
          final tracking = d['tracking'] as Map<String, dynamic>? ?? {};
          final bullPct = (sentiment['bullish_pct'] as num?)?.toDouble() ?? 50;
          final bearPct = (sentiment['bearish_pct'] as num?)?.toDouble() ?? 50;

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Text('Markets', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: AppColors.text)),
              const SizedBox(height: 4),
              const Text('Derivatives · funding · liquidation map · BTC & Gold focus', style: TextStyle(fontSize: 11, color: AppColors.textMuted)),
              const SizedBox(height: 12),
              if (live.marketPrep != null) ...[
                AlphaMarketsPanel(prep: live.marketPrep!),
                const SizedBox(height: 12),
              ],
              if (focusTracker.isNotEmpty)
                BtcGoldTracker(
                  items: focusTracker,
                  onTap: (item) => openSymbolChart(
                    context,
                    item['symbol']?.toString() ?? '',
                    tracker: item,
                  ),
                ),
              const SizedBox(height: 8),
              const Text('Charts', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.text)),
              const SizedBox(height: 8),
              ...focus.map((c) => _FocusChartCard(coin: c, formatPrice: _formatPrice)),
              const SizedBox(height: 8),
              PremiumCard(
                highlight: true,
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('MEME SENTIMENT', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1)),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('🟢 Bullish ${bullPct.toStringAsFixed(0)}%', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.profit)),
                              const SizedBox(height: 4),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(4),
                                child: LinearProgressIndicator(value: bullPct / 100, minHeight: 8, backgroundColor: AppColors.border, color: AppColors.profit),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Bearish ${bearPct.toStringAsFixed(0)}%', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.accentBlue)),
                              const SizedBox(height: 4),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(4),
                                child: LinearProgressIndicator(value: bearPct / 100, minHeight: 8, backgroundColor: AppColors.border, color: AppColors.accentBlue),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Today ${tracking['today_total'] ?? 0}/${tracking['cap'] ?? 150} signals',
                      style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                    ),
                  ],
                ),
              ),
              if (highlights.isNotEmpty) ...[
                const SizedBox(height: 14),
                const Text('Other Majors', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.text)),
                const SizedBox(height: 8),
                ...highlights.map((h) => _MarketTile(coin: h, formatPrice: _formatPrice, onTap: () => openSymbolChart(context, h['symbol'] ?? '', signal: _firstSignal(h)))),
              ],
              const SizedBox(height: 16),
              Text('Meme Coins (${coins.length})', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.text)),
              const SizedBox(height: 8),
              ...coins.map((c) => _MarketTile(coin: c, formatPrice: _formatPrice, onTap: () => openSymbolChart(context, c['symbol'] ?? '', signal: _firstSignal(c)))),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: AppColors.accent)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: AppColors.loss))),
      ),
    );
  }
}

Map<String, dynamic>? _firstSignal(Map<String, dynamic> coin) {
  final list = coin['signals'] as List?;
  if (list == null || list.isEmpty) return null;
  return list.first as Map<String, dynamic>;
}

class _FocusChartCard extends ConsumerStatefulWidget {
  final Map<String, dynamic> coin;
  final String Function(double) formatPrice;

  const _FocusChartCard({required this.coin, required this.formatPrice});

  @override
  ConsumerState<_FocusChartCard> createState() => _FocusChartCardState();
}

class _FocusChartCardState extends ConsumerState<_FocusChartCard> {
  List<Map<String, dynamic>> _candles = [];
  bool _loading = true;
  int _signalIdx = 0;

  @override
  void initState() {
    super.initState();
    _loadCandles();
  }

  List<Map<String, dynamic>> get _signals =>
      (widget.coin['signals'] as List? ?? []).cast<Map<String, dynamic>>();

  Map<String, dynamic>? get _activeSignal =>
      _signals.isEmpty ? null : _signals[_signalIdx.clamp(0, _signals.length - 1)];

  Future<void> _loadCandles() async {
    setState(() => _loading = true);
    try {
      final api = ref.read(apiServiceProvider);
      final sym = widget.coin['symbol'] as String? ?? '';
      final c = await api.fetchCandles(sym, interval: '5m', limit: 80);
      if (mounted) setState(() => _candles = c);
    } catch (_) {
      if (mounted) setState(() => _candles = []);
    }
    if (mounted) setState(() => _loading = false);
  }

  double? _d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v');

  @override
  Widget build(BuildContext context) {
    final coin = widget.coin;
    final change = (coin['change_pct_24h'] as num?)?.toDouble() ?? 0;
    final price = (coin['last_price'] as num?)?.toDouble() ?? 0;
    final isUp = change >= 0;
    final changeColor = isUp ? AppColors.profit : AppColors.loss;
    final base = coin['base'] ?? '';
    final icon = coin['icon'] ?? '🪙';
    final sig = _activeSignal;
    final tracker = widget.coin['tracker'] as Map<String, dynamic>?;
    final chart = (widget.coin['chart'] as Map<String, dynamic>?) ??
        (tracker?['chart'] as Map<String, dynamic>?);
    final newsCtx = (widget.coin['news_context'] as Map<String, dynamic>?) ??
        (tracker?['news_context'] as Map<String, dynamic>?);

    final entry = _d(sig?['entry_price']) ?? _d(chart?['strategy_line']);
    final sl = _d(sig?['stop_loss_price']) ?? _d(chart?['stop_loss']);
    final target = _d(sig?['target_1_price']) ?? _d(chart?['target']);
    final support = _d(chart?['support']);
    final resistance = _d(chart?['resistance']);
    final strategyLine = _d(chart?['strategy_line']);
    final expLow = _d(chart?['expected_move_low']);
    final expHigh = _d(chart?['expected_move_high']);
    final prediction = chart?['prediction'] as String? ?? tracker?['prediction'] as String?;
    final chartNote = chart?['note'] as String? ?? '';
    final strategyLabel = tracker?['strategy_label'] as String? ?? sig?['setup'] as String? ?? '';
    final suggestion = tracker?['suggestion'] as String? ?? '';
    final direction = sig?['direction'] as String?;
    final refPnl = _d(sig?['live_pnl_inr'] ?? sig?['ref_pnl_inr']);

    return InkWell(
      onTap: () => openSymbolChart(
        context,
        coin['symbol'] ?? '',
        signal: sig,
        tracker: tracker,
        validityPoints: (sig?['validity_points'] as List?)?.cast<String>() ?? [],
      ),
      borderRadius: BorderRadius.circular(14),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.accent.withValues(alpha: 0.4), width: 1.5),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(icon, style: const TextStyle(fontSize: 24)),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('$base / USDT', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16, color: AppColors.text)),
                      Text(widget.formatPrice(price), style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
                    ],
                  ),
                ),
                Text('${isUp ? '+' : ''}${change.toStringAsFixed(2)}%', style: TextStyle(fontWeight: FontWeight.w800, color: changeColor)),
              ],
            ),
            if (_signals.length > 1) ...[
              const SizedBox(height: 8),
              Row(
                children: List.generate(_signals.length, (i) {
                  final d = _signals[i]['direction'] as String? ?? '';
                  final on = i == _signalIdx;
                  return Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: GestureDetector(
                      onTap: () => setState(() => _signalIdx = i),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: on ? AppColors.accent.withValues(alpha: 0.25) : AppColors.bgElevated,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: on ? AppColors.accent : AppColors.border),
                        ),
                        child: Text(d, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: on ? AppColors.accent : AppColors.textMuted)),
                      ),
                    ),
                  );
                }),
              ),
            ],
            const SizedBox(height: 10),
            TradingChart(
              candles: _candles,
              entry: entry,
              stopLoss: sl,
              target: target,
              support: support,
              resistance: resistance,
              strategyLine: strategyLine,
              expectedMoveLow: expLow,
              expectedMoveHigh: expHigh,
              prediction: prediction,
              interval: '5m',
              loading: _loading,
            ),
            if (strategyLabel.isNotEmpty || chartNote.isNotEmpty || newsCtx != null) ...[
              const SizedBox(height: 10),
              if (strategyLabel.isNotEmpty)
                Text('Strategy: $strategyLabel', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.accentBlue)),
              if (chartNote.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(chartNote, style: const TextStyle(fontSize: 10, color: AppColors.gold)),
                ),
              if (suggestion.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(suggestion, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                ),
              if (newsCtx != null && (newsCtx['headline'] as String? ?? '').isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    '📰 ${newsCtx['headline']} (${newsCtx['bias'] ?? 'neutral'})',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
                  ),
                ),
            ],
            if (sig != null) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  _LevelChip('Entry', widget.formatPrice(entry ?? 0), AppColors.accent),
                  const SizedBox(width: 6),
                  _LevelChip('TP1', widget.formatPrice(target ?? 0), AppColors.profit),
                  const SizedBox(width: 6),
                  _LevelChip('Conf', '${sig['confidence'] ?? 0}%', AppColors.gold),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                '${direction ?? ''} · ${sig['setup'] ?? ''}',
                style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
              ),
            ] else
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('No live signal yet — chart updates when setup fires', style: TextStyle(fontSize: 10, color: AppColors.textMuted)),
              ),
            const SizedBox(height: 4),
            const Text('Tap for full chart + entry reason', style: TextStyle(fontSize: 10, color: AppColors.accent)),
          ],
        ),
      ),
    );
  }
}

class _LevelChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _LevelChip(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withValues(alpha: 0.35)),
        ),
        child: Column(
          children: [
            Text(label, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w700)),
            Text(value, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: color)),
          ],
        ),
      ),
    );
  }
}

class _MarketTile extends StatelessWidget {
  final Map<String, dynamic> coin;
  final String Function(double) formatPrice;
  final VoidCallback onTap;

  const _MarketTile({required this.coin, required this.formatPrice, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final change = (coin['change_pct_24h'] as num?)?.toDouble() ?? 0;
    final price = (coin['last_price'] as num?)?.toDouble() ?? 0;
    final isUp = change >= 0;
    final changeColor = isUp ? AppColors.profit : AppColors.loss;
    final base = coin['base'] ?? coin['symbol']?.toString().replaceAll('USDT', '') ?? '';
    final icon = coin['icon'] ?? '🪙';
    final status = coin['trade_status'] as String?;
    final sigCount = (coin['signals'] as List?)?.length ?? 0;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            Text(icon, style: const TextStyle(fontSize: 22)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(base, style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.text, fontSize: 15)),
                      const SizedBox(width: 4),
                      Text('/USDT', style: TextStyle(fontSize: 10, color: AppColors.textMuted.withValues(alpha: 0.7))),
                      if (status != null) ...[
                        const SizedBox(width: 8),
                        _StatusBadge(status: status),
                      ],
                      if (sigCount > 0) ...[
                        const SizedBox(width: 6),
                        Text('$sigCount signal', style: const TextStyle(fontSize: 9, color: AppColors.accent)),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(formatPrice(price), style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: changeColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '${isUp ? '+' : ''}${change.toStringAsFixed(2)}%',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: changeColor),
                  ),
                ),
                const SizedBox(height: 4),
                Text(isUp ? 'Bullish' : 'Bearish', style: TextStyle(fontSize: 9, color: changeColor)),
              ],
            ),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right, color: AppColors.textMuted, size: 18),
          ],
        ),
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'WIN' => AppColors.profit,
      'LOSS' => AppColors.loss,
      'OPEN' => AppColors.accentBlue,
      _ => AppColors.textMuted,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(4)),
      child: Text(status, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, color: color)),
    );
  }
}
