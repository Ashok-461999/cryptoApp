import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../utils/price_format.dart';
import '../models/account.dart';
import '../providers/providers.dart';
import '../screens/signal_chart_screen.dart';
import '../theme/app_theme.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) {
      ref.invalidate(tradeHistoryProvider);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final history = ref.watch(tradeHistoryProvider);
    final trading = ref.watch(tradingSettingsProvider);

    return RefreshIndicator(
      color: AppColors.accent,
      onRefresh: () async => ref.invalidate(tradeHistoryProvider),
      child: history.when(
        data: (data) {
          final summary = data['summary'] as Map<String, dynamic>? ?? {};
          final tracking = data['tracking'] as Map<String, dynamic>? ?? {};
          final todayTrades = (data['today_trades'] as List? ?? []).map((e) => TradeRecord.fromJson(e as Map<String, dynamic>)).toList();
          final items = todayTrades.isNotEmpty
              ? todayTrades
              : (data['items'] as List? ?? []).map((e) => TradeRecord.fromJson(e as Map<String, dynamic>)).toList();
          final todayTotal = tracking['today_total'] ?? items.length;
          final cap = tracking['cap'] ?? 40;
          final todayWins = tracking['wins'] ?? 0;
          final todayLosses = tracking['losses'] ?? 0;
          final todayOpen = tracking['open'] ?? 0;

          if (items.isEmpty) {
            return ListView(
              padding: const EdgeInsets.all(16),
              children: const [
                Text('Trade History', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.text)),
                SizedBox(height: 12),
                Text('No trades taken today — tap TAKE on live signals you enter on Binance.', style: TextStyle(color: AppColors.textMuted)),
              ],
            );
          }

          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: items.length + 3,
            itemBuilder: (ctx, i) {
              if (i == 0) {
                return const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Text('Today\'s Trades', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.text)),
                );
              }
              if (i == 1) {
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: PremiumCard(
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Tracking $todayTotal / $cap entries', style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.text)),
                              Text('Open $todayOpen · Win $todayWins · Loss $todayLosses', style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
                            ],
                          ),
                        ),
                        Text(
                          'All-time W ${summary['wins'] ?? 0} L ${summary['losses'] ?? 0}',
                          style: const TextStyle(fontSize: 11, color: AppColors.accent),
                        ),
                      ],
                    ),
                  ),
                );
              }
              if (i == 2) {
                final binanceToday = trading.maybeWhen(
                  data: (cfg) => cfg['binance_today_pnl_inr'],
                  orElse: () => null,
                );
                final pnlSource = summary['pnl_source'] ?? (binanceToday != null ? 'binance' : 'reference');
                final pnlToday = pnlSource == 'binance'
                    ? (binanceToday ?? summary['binance_today_pnl_inr'] ?? summary['total_pnl_inr'] ?? 0)
                    : (summary['total_pnl_inr'] ?? 0);
                final pnlNum = pnlToday is num ? pnlToday.toDouble() : double.tryParse('$pnlToday') ?? 0;
                final label = pnlSource == 'binance' ? 'Binance PnL today' : 'PnL today';
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(
                    '$label ${pnlNum >= 0 ? '+' : ''}₹${pnlNum.toStringAsFixed(0)} · entry, SL, exit, WIN/LOSS',
                    style: TextStyle(
                      fontSize: 11,
                      color: pnlSource == 'binance'
                          ? (pnlNum >= 0 ? AppColors.profit : AppColors.loss)
                          : AppColors.textMuted,
                      fontWeight: pnlSource == 'binance' ? FontWeight.w700 : FontWeight.normal,
                    ),
                  ),
                );
              }
              return _HistoryCard(trade: items[i - 3]);
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: AppColors.accent)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: AppColors.loss))),
      ),
    );
  }
}

class _HistoryCard extends StatelessWidget {
  final TradeRecord trade;
  const _HistoryCard({required this.trade});

  static String _formatTradeTime(String iso) {
    try {
      final dt = DateTime.parse(iso).toLocal();
      final diff = DateTime.now().difference(dt);
      final ago = diff.inMinutes < 60 ? '${diff.inMinutes}m ago' : '${diff.inHours}h ago';
      return 'Entry: ${DateFormat('dd MMM · HH:mm:ss').format(dt)} · $ago';
    } catch (_) {
      return iso;
    }
  }

  String _outcomeTitle() {
    return switch (trade.displayStatus) {
      'WIN' => '✅ PROFIT',
      'LOSS' => '❌ LOSS',
      'EXPIRED' => '⏱ EXPIRED / TIMEOUT',
      'OPEN' => '📡 LIVE TRADE',
      _ => trade.displayStatus,
    };
  }

  String _pnlLine() {
    if (trade.displayStatus == 'OPEN') {
      if (trade.unrealizedPnlInr != null) {
        final u = trade.unrealizedPnlInr!;
        final sign = u >= 0 ? '+' : '';
        if (trade.atSl) return '⛔ AT SL — Unrealized $sign₹${u.toStringAsFixed(0)}';
        if (trade.atTarget) return '🎯 AT TARGET — Unrealized $sign₹${u.toStringAsFixed(0)}';
        return 'Live P&L: $sign₹${u.toStringAsFixed(0)}';
      }
      return 'Tracking live — waiting for SL or target';
    }
    if (trade.displayStatus == 'LOSS') {
      return 'SL Hit · Loss ₹${trade.pnlInr.abs().toStringAsFixed(0)}';
    }
    if (trade.displayStatus == 'WIN') {
      return 'Target Hit · Profit +₹${trade.pnlInr.toStringAsFixed(0)}';
    }
    if (trade.status == 'EXPIRED' || trade.displayStatus == 'EXPIRED') {
      if (trade.pnlInr == 0) return 'Timed out after 30 min — no SL/T1 hit · Result: FLAT ₹0';
      final sign = trade.pnlInr >= 0 ? '+' : '';
      final label = trade.pnlInr >= 0 ? 'small profit' : 'small loss';
      return 'Timed out (30m) — closed at market · $label $sign₹${trade.pnlInr.abs().toStringAsFixed(0)}';
    }
    final sign = trade.pnlInr >= 0 ? '+' : '';
    return 'P&L: $sign₹${trade.pnlInr.toStringAsFixed(0)}';
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (trade.displayStatus) {
      'WIN' => AppColors.profit,
      'LOSS' => AppColors.loss,
      'OPEN' => AppColors.accent,
      _ => AppColors.textMuted,
    };
    final reasonLabel = switch (trade.closeReason) {
      'SL_HIT' => 'SL Hit',
      'T1_HIT' => 'Target 1 Hit',
      'T2_HIT' => 'Target 2 Hit',
      'TIMEOUT_PROFIT' => 'Timeout · Profit',
      'TIMEOUT_LOSS' => 'Timeout · Loss',
      'EXPIRED' => 'Timed Out',
      _ => trade.closeReason ?? '',
    };

    return InkWell(
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => SignalChartScreen(
            symbol: trade.symbol,
            direction: trade.direction,
            setup: trade.setup,
            entry: trade.entryPrice,
            stopLoss: trade.stopLossPrice,
            target: trade.target1Price,
            decisionReason: 'Historical trade #${trade.id} · ${trade.closeReason ?? trade.status}',
          ),
        ),
      ),
      borderRadius: BorderRadius.circular(12),
      child: Card(
      color: AppColors.card,
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: statusColor.withValues(alpha: 0.35)),
              ),
              child: Text(_outcomeTitle(), style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: statusColor)),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Text('#${trade.id}', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(color: statusColor.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(6)),
                  child: Text(trade.displayStatus, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: statusColor)),
                ),
                if (reasonLabel.isNotEmpty && trade.displayStatus != 'OPEN') ...[
                  const SizedBox(width: 6),
                  Text(reasonLabel, style: TextStyle(fontSize: 10, color: statusColor.withValues(alpha: 0.9))),
                ],
                const Spacer(),
                Text('${trade.leverage}x', style: const TextStyle(fontSize: 11, color: AppColors.accent, fontWeight: FontWeight.w700)),
              ],
            ),
            const SizedBox(height: 6),
            Text('${trade.direction} ${trade.symbol} · ${trade.setup}', style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.text)),
            if (trade.createdAt.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(_formatTradeTime(trade.createdAt), style: const TextStyle(fontSize: 11, color: AppColors.accentBlue, fontWeight: FontWeight.w600)),
            ],
            const SizedBox(height: 8),
            _InfoRow('Margin', '₹${trade.marginInr.toStringAsFixed(0)}'),
            _InfoRow('Position', '₹${trade.effectivePositionInr.toStringAsFixed(0)} (${trade.leverage}x = margin × leverage)'),
            _InfoRow('Stop Loss', '${formatPrice(trade.stopLossPrice)} (max loss ₹${trade.effectiveMaxLossInr.toStringAsFixed(0)} on position)'),
            _InfoRow('Target', '${formatPrice(trade.target1Price)} (profit ₹${trade.effectiveTargetProfitInr.toStringAsFixed(0)} at T1)'),
            _InfoRow('Entry', '${formatPrice(trade.entryPrice)}${trade.livePrice != null ? ' → live ${formatPrice(trade.livePrice!)}' : ''}'),
            if (trade.exitPrice != null) _InfoRow('Exit', formatPrice(trade.exitPrice!)),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: statusColor.withValues(alpha: 0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_pnlLine(), style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: statusColor)),
                  if (trade.displayStatus != 'OPEN')
                    Text('Tap for chart', style: TextStyle(fontSize: 10, color: statusColor.withValues(alpha: 0.7))),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 110, child: Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textMuted))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 11, color: AppColors.text))),
        ],
      ),
    );
  }
}
