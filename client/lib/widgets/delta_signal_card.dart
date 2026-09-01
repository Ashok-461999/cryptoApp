import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/crypto_signal.dart';
import '../providers/live_signals_provider.dart';
import '../providers/providers.dart';
import '../screens/signal_chart_screen.dart';
import '../theme/app_theme.dart';
import '../widgets/alpha_signal_report.dart';
import '../widgets/mini_chart.dart';

class DeltaSignalCard extends ConsumerStatefulWidget {
  final CryptoSignal signal;
  final double? livePrice;
  final String Function(double) formatPrice;

  const DeltaSignalCard({
    super.key,
    required this.signal,
    this.livePrice,
    required this.formatPrice,
  });

  @override
  ConsumerState<DeltaSignalCard> createState() => _DeltaSignalCardState();
}

class _DeltaSignalCardState extends ConsumerState<DeltaSignalCard> {
  bool _expanded = false;
  bool _acting = false;
  List<Map<String, dynamic>>? _candles;
  bool _loadingChart = false;

  Future<void> _loadChart() async {
    if (_candles != null || _loadingChart) return;
    setState(() => _loadingChart = true);
    try {
      final api = ref.read(apiServiceProvider);
      final c = await api.fetchCandles(widget.signal.symbol, interval: widget.signal.chartTimeframe);
      if (mounted) setState(() => _candles = c);
    } catch (_) {}
    if (mounted) setState(() => _loadingChart = false);
  }

  Future<void> _onTake() async {
    if (_acting || widget.signal.isTaken) return;
    setState(() => _acting = true);
    final ok = await ref.read(liveSignalsProvider.notifier).takeSignal(widget.signal);
    if (mounted) {
      setState(() => _acting = false);
      if (ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(widget.signal.executedOnExchange ? 'Order placed on Binance' : 'Tracking ${widget.signal.symbol}'),
            backgroundColor: AppColors.profit,
          ),
        );
      }
    }
  }

  Future<void> _onSkip() async {
    if (_acting || widget.signal.isTaken) return;
    setState(() => _acting = true);
    await ref.read(liveSignalsProvider.notifier).skipSignal(widget.signal);
    if (mounted) setState(() => _acting = false);
  }

  Color _gradeColor(String g) {
    if (g == 'A+') return AppColors.gold;
    if (g == 'A') return AppColors.profit;
    return AppColors.accentBlue;
  }

  @override
  Widget build(BuildContext context) {
    final signal = widget.signal;
    final formatPrice = widget.formatPrice;
    final isStraddle = signal.direction == 'STRADDLE';
    final isLong = !isStraddle && signal.direction == 'LONG';
    final dirColor = isStraddle ? AppColors.gold : (isLong ? AppColors.profit : AppColors.loss);
    final price = widget.livePrice ?? signal.entryPrice;
    final score = signal.confluenceScore > 0 ? signal.confluenceScore : signal.confidence;
    final grade = signal.displayGrade;
    final deriv = signal.derivatives;
    final funding = (deriv['funding_pct_8h'] as num?)?.toDouble() ?? 0;
    final ls = (deriv['long_short_ratio'] as num?)?.toDouble() ?? 1;
    final isHigh = signal.isHighConfluence || signal.isHighPriority;
    final pnlPct = isStraddle
        ? ((price - signal.entryPrice).abs() / signal.entryPrice * 100)
        : (isLong
            ? ((price - signal.entryPrice) / signal.entryPrice * 100)
            : ((signal.entryPrice - price) / signal.entryPrice * 100));

    Widget card = Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isHigh ? AppColors.gold.withValues(alpha: 0.45) : AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(color: _gradeColor(grade).withValues(alpha: 0.2), borderRadius: BorderRadius.circular(6)),
                      child: Text(grade, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: _gradeColor(grade))),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        isStraddle
                            ? 'STRADDLE ${signal.symbol.replaceAll('USDT', '')}'
                            : '${signal.direction} ${signal.symbol.replaceAll('USDT', '')}',
                        style: TextStyle(fontWeight: FontWeight.w800, color: dirColor, fontSize: 15),
                      ),
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(formatPrice(price), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppColors.text)),
                        Text(
                          '${pnlPct >= 0 ? '+' : ''}${pnlPct.toStringAsFixed(2)}%',
                          style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: pnlPct >= 0 ? AppColors.profit : AppColors.loss),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _Chip('$score/100', AppColors.accent),
                    const SizedBox(width: 6),
                    _Chip('${signal.leverage}x', AppColors.accentBlue),
                    const SizedBox(width: 6),
                    _Chip(signal.setupLabel, AppColors.textMuted),
                  ],
                ),
                if (signal.isStraddle && signal.straddleSetup.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    signal.straddleSetup['instruction']?.toString() ?? 'BUY 1× Call + BUY 1× Put on Delta',
                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.gold, height: 1.35),
                    maxLines: _expanded ? null : 2,
                    overflow: _expanded ? TextOverflow.visible : TextOverflow.ellipsis,
                  ),
                ],
                if (signal.prediction.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(
                    signal.prediction,
                    style: const TextStyle(fontSize: 11, color: AppColors.text, height: 1.35),
                    maxLines: _expanded ? null : 2,
                    overflow: _expanded ? TextOverflow.visible : TextOverflow.ellipsis,
                  ),
                ],
                if (signal.liveStatusMessage.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(signal.liveStatusMessage, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.profit)),
                ],
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.bgElevated,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: isStraddle
                      ? Row(
                          children: [
                            Expanded(child: _TradeLevel('Entry', formatPrice(signal.entryPrice), AppColors.accent)),
                            Expanded(child: _TradeLevel('TP ↑ WIN', formatPrice(signal.target1Price), AppColors.gold)),
                            Expanded(child: _TradeLevel('TP ↓ WIN', formatPrice(signal.target2Price), AppColors.gold)),
                          ],
                        )
                      : Row(
                          children: [
                            Expanded(child: _TradeLevel('Entry', formatPrice(signal.entryPrice), AppColors.text)),
                            Expanded(child: _TradeLevel('SL', formatPrice(signal.stopLossPrice), AppColors.loss)),
                            Expanded(child: _TradeLevel('TP1', formatPrice(signal.target1Price), AppColors.profit)),
                          ],
                        ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _Chip('Fund ${funding >= 0 ? '+' : ''}${funding.toStringAsFixed(3)}%', funding.abs() > 0.01 ? AppColors.warn : AppColors.textMuted),
                    const SizedBox(width: 6),
                    _Chip('L/S ${ls.toStringAsFixed(2)}', AppColors.textMuted),
                    const Spacer(),
                    Text('${signal.riskLevel} risk', style: const TextStyle(fontSize: 9, color: AppColors.textMuted)),
                  ],
                ),
                if (_expanded) ...[
                  const SizedBox(height: 12),
                  AlphaSignalReport.fromSignal(signal, formatPrice, compact: true),
                  if (_loadingChart)
                    const Padding(padding: EdgeInsets.only(top: 10), child: Center(child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))))
                  else if (_candles != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: MiniScalpChart(
                        candles: _candles!,
                        entry: signal.entryPrice,
                        stopLoss: signal.stopLossPrice,
                        target: signal.target1Price,
                        timeframe: signal.chartTimeframe,
                      ),
                    ),
                ],
                InkWell(
                  onTap: () {
                    setState(() => _expanded = !_expanded);
                    if (_expanded) _loadChart();
                  },
                  child: Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Row(
                      children: [
                        Icon(_expanded ? Icons.expand_less : Icons.expand_more, size: 18, color: AppColors.accent),
                        const SizedBox(width: 4),
                        Text(_expanded ? 'Hide analysis' : 'Full analysis', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.accent)),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (!signal.isTaken)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _acting ? null : _onSkip,
                      style: OutlinedButton.styleFrom(foregroundColor: AppColors.textMuted, side: const BorderSide(color: AppColors.border)),
                      child: const Text('SKIP', style: TextStyle(fontWeight: FontWeight.w800)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      onPressed: _acting ? null : _onTake,
                      style: ElevatedButton.styleFrom(backgroundColor: AppColors.profit, foregroundColor: AppColors.bg),
                      child: _acting
                          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.bg))
                          : const Text('TAKE', style: TextStyle(fontWeight: FontWeight.w800)),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );

    if (isHigh) {
      card = Container(
        decoration: BoxDecoration(gradient: AppColors.gradientHighPriority, borderRadius: BorderRadius.circular(15)),
        padding: const EdgeInsets.all(2),
        child: card,
      );
    }

    return InkWell(
      onTap: () => openSignalChart(context, signal),
      borderRadius: BorderRadius.circular(14),
      child: card,
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final Color color;
  const _Chip(this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(5)),
      child: Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: color), overflow: TextOverflow.ellipsis),
    );
  }
}

class _TradeLevel extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _TradeLevel(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 9, color: AppColors.textMuted)),
        Text(value, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: color)),
      ],
    );
  }
}
