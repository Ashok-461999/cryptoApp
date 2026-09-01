import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/crypto_signal.dart';
import '../providers/live_signals_provider.dart';
import '../providers/providers.dart';
import '../screens/signal_chart_screen.dart';
import '../theme/app_theme.dart';
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
  bool _showDetails = false;
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
            content: Text(
              widget.signal.executedOnExchange
                  ? 'Order placed on Binance Futures'
                  : 'Tracking ${widget.signal.symbol}',
            ),
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

  Color _sentimentColor(String s) {
    if (s == 'bullish') return AppColors.profit;
    if (s == 'bearish') return AppColors.loss;
    return AppColors.textMuted;
  }

  @override
  Widget build(BuildContext context) {
    final signal = widget.signal;
    final formatPrice = widget.formatPrice;
    final livePrice = widget.livePrice;
    final isLong = signal.direction == 'LONG';
    final dirColor = isLong ? AppColors.profit : AppColors.loss;
    final price = livePrice ?? signal.entryPrice;
    final score = signal.confluenceScore;
    final grade = signal.displayGrade;
    final deriv = signal.derivatives;
    final mp = signal.marketProfile;
    final oi = (deriv['open_interest_usdt'] as num?)?.toDouble() ?? 0;
    final funding = (deriv['funding_pct_8h'] as num?)?.toDouble() ?? 0;
    final ls = (deriv['long_short_ratio'] as num?)?.toDouble() ?? 1;
    final taker = (deriv['taker_buy_sell_ratio'] as num?)?.toDouble() ?? 1;
    final poc = (mp['poc'] as num?)?.toDouble() ?? 0;
    final vah = (mp['vah'] as num?)?.toDouble() ?? 0;
    final val = (mp['val'] as num?)?.toDouble() ?? 0;
    final support = signal.supportPrice > 0 ? signal.supportPrice : val;
    final resist = signal.resistancePrice > 0 ? signal.resistancePrice : vah;
    final isHigh = signal.isHighConfluence || signal.isHighPriority;
    final pred = signal.predictionStatus;

    Widget card = Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: isHigh ? AppColors.gold.withValues(alpha: 0.5) : AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (signal.signalHeader.isNotEmpty)
                  Text(signal.signalHeader, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.gold, height: 1.3)),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Text('${signal.confluenceEmoji} ', style: const TextStyle(fontSize: 14)),
                    _Badge('CONFLUENCE ${score > 0 ? score : signal.confidence}/100', AppColors.accent),
                    const SizedBox(width: 6),
                    _Badge('Grade $grade', _gradeColor(grade)),
                    const SizedBox(width: 6),
                    _Badge('${signal.leverage}x', AppColors.accentBlue),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  '${signal.direction} ${signal.symbol.replaceAll('USDT', '')} · ${signal.instrumentType} · ${signal.holdingStyle}',
                  style: TextStyle(fontWeight: FontWeight.w800, color: dirColor, fontSize: 14),
                ),
                const SizedBox(height: 4),
                Text(
                  'Delta × Binance Alpha · ${signal.setupLabel} · ${signal.riskLevel} risk',
                  style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
                ),
                const SizedBox(height: 10),
                if (signal.prediction.isNotEmpty)
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.bgElevated,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.border.withValues(alpha: 0.5)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('PREDICTION', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.accentBlue, letterSpacing: 0.8)),
                        const SizedBox(height: 4),
                        Text(signal.prediction, style: const TextStyle(fontSize: 11, color: AppColors.text, height: 1.4)),
                      ],
                    ),
                  ),
                const SizedBox(height: 10),
                if (signal.newsHeadline.isNotEmpty)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.newspaper, size: 14, color: _sentimentColor(signal.newsSentiment)),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          '${signal.newsImpact.toUpperCase()} · ${signal.newsSentiment} (${signal.newsSentimentScore >= 0 ? '+' : ''}${signal.newsSentimentScore}) · ${signal.newsEffect}\n${signal.newsHeadline}',
                          style: TextStyle(fontSize: 10, color: _sentimentColor(signal.newsSentiment), height: 1.35),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                if (signal.liveStatusMessage.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.profit.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(signal.liveStatusMessage, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.profit)),
                  ),
                ],
                const SizedBox(height: 10),
                _SectionTitle('STRUCTURE'),
                _SectionBody(_structureLines(signal, formatPrice)),
                const SizedBox(height: 8),
                _SectionTitle('DERIVATIVES MAP'),
                _DerivRow(oi: oi, funding: funding, ls: ls, taker: taker),
                Text(
                  'OI chg ${(deriv['oi_change_24h_pct'] as num?)?.toStringAsFixed(1) ?? '0'}% · CVD ${deriv['cvd_trend'] ?? 'flat'} · ${deriv['cvd_confirming'] == true ? 'Confirming' : 'Diverging'} · ${deriv['funding_regime'] ?? 'neutral'}',
                  style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.3),
                ),
                Text(
                  'Liq above ${formatPrice((deriv['liquidation']?['cluster_above'] as num?)?.toDouble() ?? 0)} (${deriv['liquidation']?['density'] ?? 'low'}) · below ${formatPrice((deriv['liquidation']?['cluster_below'] as num?)?.toDouble() ?? 0)}',
                  style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.3),
                ),
                const SizedBox(height: 8),
                _SectionTitle('GEX / OPTIONS (DELTA)'),
                _SectionBody(_gexLines(signal.optionsGex)),
                const SizedBox(height: 8),
                _SectionTitle('MARKET PROFILE'),
                if (poc > 0)
                  Text(
                    'Profile POC ${formatPrice(poc)} · VAH ${formatPrice(vah)} · VAL ${formatPrice(val)} · ${mp['position'] ?? ''}',
                    style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.3),
                  ),
                if (signal.htfSummary.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(signal.htfSummary, style: const TextStyle(fontSize: 10, color: AppColors.accentBlue, height: 1.3)),
                ],
                const Divider(height: 20, color: AppColors.border),
                Row(
                  children: [
                    Expanded(child: _LevelChip('Support', formatPrice(support), AppColors.profit)),
                    const SizedBox(width: 6),
                    Expanded(child: _LevelChip('Resist', formatPrice(resist), AppColors.loss)),
                  ],
                ),
                const SizedBox(height: 8),
                _Row('Entry', formatPrice(signal.entryPrice)),
                _Row('TP1', formatPrice(signal.target1Price), valueColor: AppColors.profit),
                if (signal.target2Price > 0) _Row('TP2', formatPrice(signal.target2Price), valueColor: AppColors.profit),
                if (signal.target3Price > 0) _Row('TP3', formatPrice(signal.target3Price), valueColor: AppColors.profit),
                _Row('STRICT SL', formatPrice(signal.stopLossPrice), valueColor: AppColors.loss, bold: true),
                if (signal.expectedMovePct > 0)
                  _Row('Expected move', '${signal.expectedMovePct.toStringAsFixed(1)}% to TP1', valueColor: AppColors.gold),
                _Row('Liquidation', formatPrice(signal.liquidationPrice)),
                if (signal.invalidation.isNotEmpty) _Row('Invalidation', signal.invalidation),
                if (signal.managementRules.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  _SectionTitle('MANAGEMENT'),
                  ...signal.managementRules.map((r) => Text('• $r', style: const TextStyle(fontSize: 10, color: AppColors.textMuted))),
                ],
                if (pred['check_2h'] != null || pred['check_6h'] != null) ...[
                  const SizedBox(height: 6),
                  if (pred['check_2h'] != null) Text('${pred['check_2h']}', style: const TextStyle(fontSize: 10, color: AppColors.accentBlue)),
                  if (pred['check_6h'] != null) Text('${pred['check_6h']}', style: const TextStyle(fontSize: 10, color: AppColors.accent)),
                ],
                _Row('Margin', '₹${signal.marginInr.toStringAsFixed(0)} · max ${signal.maxLeverageGrade}x for grade'),
                _Row('Live', '${formatPrice(price)}', bold: true),
                Text('Signal: ${signal.signalTimeLabel}', style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                if (signal.confluenceFactors.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  InkWell(
                    onTap: () {
                      setState(() => _showDetails = !_showDetails);
                      if (_showDetails) _loadChart();
                    },
                    child: Row(
                      children: [
                        Icon(_showDetails ? Icons.expand_less : Icons.expand_more, color: AppColors.accent, size: 18),
                        const SizedBox(width: 4),
                        const Text('Confluence breakdown', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.accent)),
                      ],
                    ),
                  ),
                  if (_showDetails) ...[
                    ...signal.confluenceFactors.map((f) => Padding(
                          padding: const EdgeInsets.only(top: 4, left: 8),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('• ', style: TextStyle(color: AppColors.accent, fontSize: 11)),
                              Expanded(child: Text(f, style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.35))),
                            ],
                          ),
                        )),
                    if (_candles != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: MiniScalpChart(
                          candles: _candles!,
                          entry: signal.entryPrice,
                          stopLoss: signal.stopLossPrice,
                          target: signal.target1Price,
                          timeframe: '${signal.chartTimeframe} / ${signal.entryTimeframe}',
                        ),
                      ),
                  ],
                ],
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
                          : const Text('TAKE TRADE', style: TextStyle(fontWeight: FontWeight.w800)),
                    ),
                  ),
                ],
              ),
            ),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.loss.withValues(alpha: 0.1),
              borderRadius: const BorderRadius.only(bottomLeft: Radius.circular(14), bottomRight: Radius.circular(14)),
            ),
            child: Text(
              '⚠️ STRICT SL ${formatPrice(signal.stopLossPrice)} · Leverage capped by grade · Educational only',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.loss),
            ),
          ),
        ],
      ),
    );

    if (isHigh) {
      card = Container(
        decoration: BoxDecoration(
          gradient: AppColors.gradientHighPriority,
          borderRadius: BorderRadius.circular(15),
        ),
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

List<String> _structureLines(CryptoSignal signal, String Function(double) formatPrice) {
  final s = signal.structureAnalysis;
  if (s.isEmpty) return [signal.htfSummary];
  return [
    'HTF ${s['htf_bias'] ?? signal.htfBias} — ${s['bos_choch'] ?? ''}',
    'Sweep: ${s['sweep'] ?? ''} @ ${formatPrice((s['sweep_level'] as num?)?.toDouble() ?? 0)}',
    'Entry: ${s['entry_zone'] ?? ''}',
    'Invalidation: ${s['invalidation'] ?? signal.invalidation}',
  ];
}

List<String> _gexLines(Map<String, dynamic> optionsGex) {
  if (optionsGex['available'] != true) {
    return [optionsGex['reason']?.toString() ?? 'GEX data unavailable for this pair'];
  }
  final g = optionsGex['options'] as Map<String, dynamic>? ?? {};
  final flow = optionsGex['options_flow'] as Map<String, dynamic>? ?? {};
  return [
    'Zero γ ${g['zero_gamma']} · Net GEX ${g['net_gex_sign'] ?? g['net_gex']}',
    'Call wall ${g['call_wall']} · Put wall ${g['put_wall']} · Max pain ${g['max_pain']}',
    'IV pct ${g['iv_percentile']}% · ${optionsGex['strategy_hint'] ?? ''}',
    if (flow['flow_bias'] != null) 'Whale flow: ${flow['flow_bias']}',
  ];
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle(this.title);
  @override
  Widget build(BuildContext context) {
    return Text(title, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.accentBlue, letterSpacing: 0.8));
  }
}

class _SectionBody extends StatelessWidget {
  final List<String> lines;
  const _SectionBody(this.lines);
  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: lines.map((l) => Text(l, style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.35))).toList(),
    );
  }
}

class _Badge extends StatelessWidget {
  final String label;
  final Color color;
  const _Badge(this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.2), borderRadius: BorderRadius.circular(6)),
      child: Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: color)),
    );
  }
}

class _DerivRow extends StatelessWidget {
  final double oi;
  final double funding;
  final double ls;
  final double taker;
  const _DerivRow({required this.oi, required this.funding, required this.ls, required this.taker});

  @override
  Widget build(BuildContext context) {
    final oiM = oi >= 1e6 ? '\$${(oi / 1e6).toStringAsFixed(0)}M' : '\$${oi.toStringAsFixed(0)}';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.bgElevated,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Expanded(child: _Mini('OI', oiM)),
          Expanded(child: _Mini('Fund', '${funding >= 0 ? '+' : ''}${funding.toStringAsFixed(3)}%')),
          Expanded(child: _Mini('L/S', ls.toStringAsFixed(2))),
          Expanded(child: _Mini('Taker', taker.toStringAsFixed(2))),
        ],
      ),
    );
  }
}

class _Mini extends StatelessWidget {
  final String k;
  final String v;
  const _Mini(this.k, this.v);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(k, style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: AppColors.textMuted)),
        Text(v, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.text)),
      ],
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: color)),
          Text(value, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: color)),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  final bool bold;
  const _Row(this.label, this.value, {this.valueColor, this.bold = false});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(width: 90, child: Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textMuted))),
          Expanded(child: Text(value, style: TextStyle(fontSize: 12, fontWeight: bold ? FontWeight.w700 : FontWeight.w500, color: valueColor ?? AppColors.text))),
        ],
      ),
    );
  }
}
