import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'dart:async';

import '../models/account.dart';
import '../models/crypto_signal.dart';
import '../providers/live_signals_provider.dart';
import '../providers/providers.dart';
import '../screens/signal_chart_screen.dart';
import '../widgets/btc_gold_tracker.dart';
import '../widgets/mini_chart.dart';
import '../theme/app_theme.dart';

class SignalsScreen extends ConsumerStatefulWidget {
  const SignalsScreen({super.key});

  @override
  ConsumerState<SignalsScreen> createState() => _SignalsScreenState();
}

enum _CategoryFilter { all, top, btcGold, majors, meme, alts }

class _SignalsScreenState extends ConsumerState<SignalsScreen> {
  _CategoryFilter _filter = _CategoryFilter.all;
  Timer? _marketsTimer;

  @override
  void initState() {
    super.initState();
    _marketsTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      ref.invalidate(marketsProvider);
    });
  }

  @override
  void dispose() {
    _marketsTimer?.cancel();
    super.dispose();
  }

  List<CryptoSignal> _applyFilter(List<CryptoSignal> list) {
    return switch (_filter) {
      _CategoryFilter.top => list.where((s) => s.isTopStrategy).toList(),
      _CategoryFilter.btcGold => list.where((s) => s.symbol == 'BTCUSDT' || s.symbol == 'PAXGUSDT').toList(),
      _CategoryFilter.majors => list.where((s) => s.category == 'major').toList(),
      _CategoryFilter.meme => list.where((s) => s.category == 'meme').toList(),
      _CategoryFilter.alts => list.where((s) => s.category == 'alt').toList(),
      _ => list,
    };
  }

  String _formatPrice(double p) {
    if (p >= 1000) return NumberFormat('#,##0.00').format(p);
    if (p >= 1) return p.toStringAsFixed(4);
    return p.toStringAsFixed(8);
  }

  @override
  Widget build(BuildContext context) {
    final live = ref.watch(liveSignalsProvider);
    final trading = ref.watch(tradingSettingsProvider);
    final markets = ref.watch(marketsProvider);
    final filtered = List<CryptoSignal>.from(_applyFilter(live.signals))
      ..sort((a, b) {
        final ah = a.isHighPriority ? 0 : 1;
        final bh = b.isHighPriority ? 0 : 1;
        if (ah != bh) return ah.compareTo(bh);
        return b.confidence.compareTo(a.confidence);
      });

    return RefreshIndicator(
      color: AppColors.accent,
      onRefresh: () async {
        ref.read(liveSignalsProvider.notifier).connect();
      },
      child: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Row(
                children: [
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ScalpTrack', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.text)),
                        SizedBox(height: 4),
                        Text('Live signals · you choose TAKE or SKIP', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                      ],
                    ),
                  ),
                  _LiveBadge(connected: live.connected),
                ],
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: markets.when(
                data: (m) {
                  final tracker = (m['focus_tracker'] as List? ?? [])
                      .cast<Map<String, dynamic>>();
                  if (tracker.isEmpty) return const SizedBox.shrink();
                  return BtcGoldTracker(
                    items: tracker,
                    onTap: (item) => openSymbolChart(
                      context,
                      item['symbol']?.toString() ?? '',
                      tracker: item,
                    ),
                  );
                },
                loading: () => const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Center(child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accent))),
                ),
                error: (_, __) => const SizedBox.shrink(),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: trading.when(
                data: (cfg) => _DailyGoalBanner(
                  takeCount: live.takeCountToday,
                  takeCap: live.takeCapLabel,
                  totalScanned: live.totalScanned,
                  lastClosed: live.lastClosedMessage,
                  tradingConfig: cfg,
                ),
                loading: () => _DailyGoalBanner(
                  takeCount: live.takeCountToday,
                  takeCap: live.takeCapLabel,
                  totalScanned: live.totalScanned,
                  lastClosed: live.lastClosedMessage,
                ),
                error: (_, __) => _DailyGoalBanner(
                  takeCount: live.takeCountToday,
                  takeCap: live.takeCapLabel,
                  totalScanned: live.totalScanned,
                  lastClosed: live.lastClosedMessage,
                  serverOffline: true,
                ),
              ),
            ),
          ),
          if (live.recentClosed.isNotEmpty)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Recent Results', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.text)),
                    const SizedBox(height: 8),
                    ...live.recentClosed.take(3).map((t) => _ClosedTradeChip(trade: t)),
                  ],
                ),
              ),
            ),
          if (live.error != null)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.loss.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.loss.withValues(alpha: 0.4)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Cannot reach AWS server', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.loss, fontSize: 13)),
                      const SizedBox(height: 6),
                      Text(live.error!, style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                      const SizedBox(height: 6),
                      const Text(
                        'Server: 13.201.83.70 · Auto-reconnecting every 5s\n'
                        'Check your internet connection.',
                        style: TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.4),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _FilterChip(label: 'All', selected: _filter == _CategoryFilter.all, onTap: () => setState(() => _filter = _CategoryFilter.all)),
                    const SizedBox(width: 8),
                    _FilterChip(label: 'AMD/Liq', selected: _filter == _CategoryFilter.top, onTap: () => setState(() => _filter = _CategoryFilter.top)),
                    const SizedBox(width: 6),
                    _FilterChip(label: 'BTC/Gold', selected: _filter == _CategoryFilter.btcGold, onTap: () => setState(() => _filter = _CategoryFilter.btcGold)),
                    const SizedBox(width: 8),
                    _FilterChip(label: 'Majors', selected: _filter == _CategoryFilter.majors, onTap: () => setState(() => _filter = _CategoryFilter.majors)),
                    const SizedBox(width: 8),
                    _FilterChip(label: 'Meme', selected: _filter == _CategoryFilter.meme, onTap: () => setState(() => _filter = _CategoryFilter.meme)),
                    const SizedBox(width: 8),
                    _FilterChip(label: 'Alts', selected: _filter == _CategoryFilter.alts, onTap: () => setState(() => _filter = _CategoryFilter.alts)),
                  ],
                ),
              ),
            ),
          ),
          if (filtered.isEmpty && live.signals.isEmpty && !live.connected)
            const SliverFillRemaining(
              child: Center(child: CircularProgressIndicator(color: AppColors.accent)),
            )
          else if (filtered.isEmpty)
            SliverFillRemaining(
              child: Center(
                child: Text(
                  'No live signals yet — scanning all strategies\n(${live.totalScanned} coins · HIGH = highlighted A+)',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.textMuted.withValues(alpha: 0.8)),
                ),
              ),
            )
          else
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (ctx, i) => Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                  child: _CryptoSignalCard(
                    signal: filtered[i],
                    livePrice: live.prices[filtered[i].symbol],
                    formatPrice: _formatPrice,
                  ),
                ),
                childCount: filtered.length,
              ),
            ),
          const SliverToBoxAdapter(child: SizedBox(height: 80)),
        ],
      ),
    );
  }
}

class _LiveBadge extends StatelessWidget {
  final bool connected;
  const _LiveBadge({required this.connected});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: (connected ? AppColors.profit : AppColors.textMuted).withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: connected ? AppColors.profit : AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(
              color: connected ? AppColors.profit : AppColors.textMuted,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            connected ? 'LIVE' : 'OFF',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: connected ? AppColors.profit : AppColors.textMuted),
          ),
        ],
      ),
    );
  }
}

class _DailyGoalBanner extends StatelessWidget {
  final int takeCount;
  final String takeCap;
  final int totalScanned;
  final String? lastClosed;
  final Map<String, dynamic>? tradingConfig;
  final bool serverOffline;
  const _DailyGoalBanner({
    required this.takeCount,
    required this.takeCap,
    required this.totalScanned,
    this.lastClosed,
    this.tradingConfig,
    this.serverOffline = false,
  });

  @override
  Widget build(BuildContext context) {
    final cfg = tradingConfig;
    final usesBinance = cfg?['pnl_mode'] == 'binance' || cfg?['capital_source'] == 'binance';
    final equityInr = (cfg?['binance_equity_inr'] ?? cfg?['capital_inr'] ?? 0).toString();
    final walletUsdt = (cfg?['binance_usdt_balance'] ?? 0).toString();
    final todayPnl = (cfg?['binance_today_pnl_inr'] ?? 0);
    final todayPnlNum = todayPnl is num ? todayPnl.toDouble() : double.tryParse('$todayPnl') ?? 0;
    final unrealized = (cfg?['binance_unrealized_pnl_inr'] ?? 0);
    final unrealizedNum = unrealized is num ? unrealized.toDouble() : double.tryParse('$unrealized') ?? 0;
    final pnlColor = todayPnlNum >= 0 ? AppColors.profit : AppColors.loss;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: serverOffline ? AppColors.loss.withValues(alpha: 0.5) : AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
            const Text('ScalpTrack Live', style: TextStyle(fontWeight: FontWeight.w800, color: AppColors.text, fontSize: 20)),
          if (serverOffline) ...[
            const SizedBox(height: 6),
            const Text('Server paused — tell admin to start when ready', style: TextStyle(fontSize: 11, color: AppColors.loss, fontWeight: FontWeight.w700)),
          ] else if (usesBinance) ...[
            const SizedBox(height: 4),
            Text(
              'Binance ₹$equityInr · $walletUsdt USDT · buy dip / sell top',
              style: const TextStyle(fontSize: 11, color: AppColors.accent),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Text(
                  'Today PnL ',
                  style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                ),
                Text(
                  '${todayPnlNum >= 0 ? '+' : ''}₹${todayPnlNum.toStringAsFixed(0)}',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: pnlColor),
                ),
                const SizedBox(width: 12),
                Text(
                  'Open PnL ${unrealizedNum >= 0 ? '+' : ''}₹${unrealizedNum.toStringAsFixed(0)}',
                  style: TextStyle(fontSize: 11, color: unrealizedNum >= 0 ? AppColors.profit : AppColors.loss),
                ),
              ],
            ),
          ] else ...[
            const SizedBox(height: 4),
            Text(
              '₹20,000 reference · ₹200 risk · buy dip / sell top · 1m scalp',
              style: const TextStyle(fontSize: 11, color: AppColors.accent),
            ),
          ],
          const SizedBox(height: 4),
          Text(
            '100–150 scalps/day · 25 fast movers · scan every 1m · 1:1 R:R',
            style: const TextStyle(fontSize: 12, color: AppColors.gold, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(
            'Signals today: $takeCount · cap: $takeCap · confidence > 48% shown',
            style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
          ),
          if (lastClosed != null) ...[
            const SizedBox(height: 6),
            Text('Last: $lastClosed', style: const TextStyle(fontSize: 11, color: AppColors.accent, fontWeight: FontWeight.w600)),
          ],
          const SizedBox(height: 4),
          Text(
            'Signals refresh every 1m · prices update every ~1s',
            style: TextStyle(fontSize: 11, color: AppColors.textMuted.withValues(alpha: 0.7)),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? AppColors.accent.withValues(alpha: 0.2) : AppColors.card,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? AppColors.accent : AppColors.border),
        ),
        child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: selected ? AppColors.accent : AppColors.textMuted)),
      ),
    );
  }
}

class _CryptoSignalCard extends ConsumerStatefulWidget {
  final CryptoSignal signal;
  final double? livePrice;
  final String Function(double) formatPrice;
  const _CryptoSignalCard({required this.signal, this.livePrice, required this.formatPrice});

  @override
  ConsumerState<_CryptoSignalCard> createState() => _CryptoSignalCardState();
}

class _CryptoSignalCardState extends ConsumerState<_CryptoSignalCard> {
  bool _showWhy = false;
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
                  : 'Tracking ${widget.signal.symbol} — enable auto-execute on server for Binance orders',
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

  @override
  Widget build(BuildContext context) {
    final signal = widget.signal;
    final formatPrice = widget.formatPrice;
    final livePrice = widget.livePrice;
    final isLong = signal.direction == 'LONG';
    final dirColor = isLong ? AppColors.profit : AppColors.loss;
    final price = livePrice ?? signal.entryPrice;
    final pnlPct = isLong
        ? ((price - signal.entryPrice) / signal.entryPrice * 100)
        : ((signal.entryPrice - price) / signal.entryPrice * 100);
    final atSl = isLong ? price <= signal.stopLossPrice : price >= signal.stopLossPrice;
    final atTarget = isLong ? price >= signal.target1Price : price <= signal.target1Price;

    String refLabel() {
      final st = signal.refStatus.toUpperCase();
      if (st == 'WIN') return '✅ Ref WIN';
      if (st == 'LOSS') return '❌ Ref LOSS';
      if (st == 'EXPIRED') return '⏱ Ref EXPIRED';
      if (signal.userTaken) return '📌 You took · Ref LIVE';
      return '📊 Ref tracking';
    }
    final refPnl = signal.livePnlInr != 0 ? signal.livePnlInr : signal.refPnlInr;
    final refColor = refPnl >= 0 ? AppColors.profit : AppColors.loss;
    final refSign = refPnl >= 0 ? '+' : '';

    final isHigh = signal.isHighPriority;
    final cardOpacity = isHigh ? 1.0 : 0.72;

    Widget card = Opacity(
      opacity: cardOpacity,
      child: Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: atSl ? AppColors.loss : (isHigh ? Colors.transparent : (signal.spreadWarning ? AppColors.warn : AppColors.border)),
          width: atSl ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        signal.isTaken ? '✅ TAKEN · ${signal.direction} ${signal.symbol}' : '📡 LIVE · ${signal.direction} ${signal.symbol}',
                          style: TextStyle(fontWeight: FontWeight.w800, color: dirColor, fontSize: 14)),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(color: AppColors.accent.withValues(alpha: 0.2), borderRadius: BorderRadius.circular(6)),
                      child: Text('${signal.leverage}x', style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.accent, fontSize: 12)),
                    ),
                    if (signal.isTopStrategy) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                        decoration: BoxDecoration(color: AppColors.profit.withValues(alpha: 0.25), borderRadius: BorderRadius.circular(6)),
                        child: Text(signal.topStrategyBadge, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.profit)),
                      ),
                    ],
                    if (isHigh && signal.displayPriorityLabel.isNotEmpty) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                        decoration: BoxDecoration(
                          gradient: AppColors.gradientHighPriority,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          signal.displayPriorityLabel,
                          style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.bg),
                        ),
                      ),
                    ] else if (signal.notify || signal.confidence >= 82) ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                        decoration: BoxDecoration(gradient: AppColors.gradientPrimary, borderRadius: BorderRadius.circular(6)),
                        child: Text(
                          signal.riskReward >= 0.95 ? 'A+ 1:1' : 'SCALP',
                          style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.bg),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 6),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.bgElevated,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.border.withValues(alpha: 0.6)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.schedule, size: 14, color: AppColors.accentBlue),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Signal given: ${signal.signalTimeLabel}',
                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.accentBlue),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 6),
                Text('Tap card for chart · TAKE only if you enter on Binance', style: TextStyle(fontSize: 10, color: AppColors.accent.withValues(alpha: 0.8))),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Expanded(child: Text('Setup: ${signal.setupLabel} · ${signal.confidence}% conf', style: const TextStyle(fontSize: 12, color: AppColors.textMuted))),
                    if (signal.tradeId != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(color: AppColors.accent.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(4)),
                        child: Text('#${signal.tradeId} ${signal.status}', style: const TextStyle(fontSize: 10, color: AppColors.accent, fontWeight: FontWeight.w700)),
                      ),
                  ],
                ),
                const Divider(height: 20, color: AppColors.border),
                _Row('Live', '${formatPrice(price)}  (${pnlPct >= 0 ? '+' : ''}${pnlPct.toStringAsFixed(2)}%)',
                    valueColor: pnlPct >= 0 ? AppColors.profit : AppColors.loss, bold: true),
                if (atTarget) const Text('🎯 Target zone', style: TextStyle(fontSize: 11, color: AppColors.profit)),
                if (atSl) const Text('⛔ AT / PAST STRICT SL', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.loss)),
                _Row('Entry', formatPrice(signal.entryPrice)),
                _Row('Target', '${formatPrice(signal.target1Price)}  (+${signal.target1Pct.toStringAsFixed(1)}%)', valueColor: AppColors.profit),
                _Row('STRICT SL', '${formatPrice(signal.stopLossPrice)}  (${signal.stopLossPct.toStringAsFixed(1)}%)', valueColor: AppColors.loss, bold: true),
                const SizedBox(height: 8),
                _Row('Margin', '₹${signal.marginInr.toStringAsFixed(0)}', valueColor: AppColors.textMuted),
                _Row('Position', '₹${signal.effectivePositionInr.toStringAsFixed(0)} (${signal.leverage}x)', valueColor: AppColors.accent),
                _Row('Max loss at SL', '₹${signal.effectiveMaxLossInr.toStringAsFixed(0)}', valueColor: AppColors.loss),
                _Row('T1 profit (min)', '₹${signal.effectiveTargetProfitInr.toStringAsFixed(0)} · unlimited above', valueColor: AppColors.profit),
                _Row(refLabel(), '$refSign₹${refPnl.abs().toStringAsFixed(0)} (margin×${signal.leverage}x)', valueColor: refColor, bold: true),
                if (signal.userTaken)
                  _Row('Your trade', '#${signal.tradeId ?? "—"} · you entered on Binance', valueColor: AppColors.accent),
                if (signal.validityPoints.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  InkWell(
                    onTap: () {
                      setState(() => _showWhy = !_showWhy);
                      if (_showWhy) _loadChart();
                    },
                    child: Row(
                      children: [
                        Icon(_showWhy ? Icons.expand_less : Icons.expand_more, color: AppColors.accent, size: 18),
                        const SizedBox(width: 4),
                        const Text('Why this trade is valid', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.accent)),
                      ],
                    ),
                  ),
                  if (_showWhy)
                    ...signal.validityPoints.map((p) => Padding(
                          padding: const EdgeInsets.only(top: 4, left: 8),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('• ', style: TextStyle(color: AppColors.accent, fontSize: 11)),
                              Expanded(child: Text(p, style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.35))),
                            ],
                          ),
                        )),
                  if (_showWhy && _candles != null)
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
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.textMuted,
                        side: const BorderSide(color: AppColors.border),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('SKIP', style: TextStyle(fontWeight: FontWeight.w800)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      onPressed: _acting ? null : _onTake,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.profit,
                        foregroundColor: AppColors.bg,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('⚠️ STRICT SL: Exit at ${formatPrice(signal.stopLossPrice)}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.loss)),
                const Text('Do NOT move stop wider', style: TextStyle(fontSize: 11, color: AppColors.textMuted)),
              ],
            ),
          ),
        ],
      ),
    ),
    );

    if (isHigh && !atSl) {
      card = Container(
        decoration: BoxDecoration(
          gradient: AppColors.gradientHighPriority,
          borderRadius: BorderRadius.circular(15),
          boxShadow: [
            BoxShadow(
              color: AppColors.gold.withValues(alpha: 0.25),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
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

class _ClosedTradeChip extends StatelessWidget {
  final TradeRecord trade;
  const _ClosedTradeChip({required this.trade});

  @override
  Widget build(BuildContext context) {
    final color = switch (trade.displayStatus) {
      'WIN' => AppColors.profit,
      'LOSS' => AppColors.loss,
      _ => AppColors.textMuted,
    };
    final reason = trade.closeReason ?? trade.displayStatus;
    final sign = trade.pnlInr >= 0 ? '+' : '';

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          Text(trade.displayStatus, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: color)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${trade.direction} ${trade.symbol} · $reason · ${trade.leverage}x · Margin ₹${trade.marginInr.toStringAsFixed(0)} · Pos ₹${trade.effectivePositionInr.toStringAsFixed(0)}',
              style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
            ),
          ),
          Text('$sign₹${trade.pnlInr.toStringAsFixed(0)}', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: color)),
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
