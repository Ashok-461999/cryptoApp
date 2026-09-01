import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/account.dart';
import '../providers/providers.dart';
import '../theme/app_theme.dart';

class AccountScreen extends ConsumerWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final stats = ref.watch(accountStatsProvider);

    return RefreshIndicator(
      color: AppColors.accent,
      onRefresh: () async {
        ref.invalidate(accountStatsProvider);
        ref.invalidate(tradeHistoryProvider);
      },
      child: stats.when(
        data: (s) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text('Account', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.text)),
            const SizedBox(height: 4),
            Text(
              s.usesBinancePnl
                  ? 'Binance Futures · live balance & PnL'
                  : 'Reference mode · connect Binance API on server',
              style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
            ),
            const SizedBox(height: 16),
            _StatCard(
              title: s.usesBinancePnl ? 'Binance Equity (INR)' : 'Equity (INR)',
              value: '₹${NumberFormat('#,##0').format(s.equityInr)}',
              sub: s.usesBinancePnl
                  ? 'Wallet ₹${NumberFormat('#,##0').format(s.binanceWalletInr)} · Today PnL ₹${s.binanceTodayPnlInr.toStringAsFixed(0)}'
                  : 'Started ₹${NumberFormat('#,##0').format(s.startingCapitalInr)} · PnL ₹${s.realizedPnlInr.toStringAsFixed(0)}',
              color: (s.usesBinancePnl ? s.binanceTodayPnlInr : s.realizedPnlInr) >= 0 ? AppColors.profit : AppColors.loss,
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: _MiniStat(
                    label: s.usesBinancePnl ? 'Today PnL (Binance)' : 'Realized PnL',
                    value: '₹${(s.usesBinancePnl ? s.binanceTodayPnlInr : s.realizedPnlInr).toStringAsFixed(0)}',
                    color: (s.usesBinancePnl ? s.binanceTodayPnlInr : s.realizedPnlInr) >= 0 ? AppColors.profit : AppColors.loss,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _MiniStat(
                    label: s.usesBinancePnl ? 'Unrealized PnL' : 'Drawdown',
                    value: s.usesBinancePnl
                        ? '₹${s.binanceUnrealizedPnlInr.toStringAsFixed(0)}'
                        : '${s.drawdownPct.toStringAsFixed(1)}%',
                    color: s.usesBinancePnl
                        ? (s.binanceUnrealizedPnlInr >= 0 ? AppColors.profit : AppColors.loss)
                        : (s.drawdownPct > 5 ? AppColors.loss : AppColors.text),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            if (s.dailyPnl.isNotEmpty) ...[
              const SizedBox(height: 8),
              const Text('Daily P&L', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.text)),
              const SizedBox(height: 8),
              ...s.dailyPnl.take(7).map((d) => _DailyPnlTile(row: d)),
            ],
            if (s.setupPerformance.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text('Strategy performance', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.text)),
              const SizedBox(height: 4),
              const Text('Which setup gives more profit vs loss', style: TextStyle(fontSize: 11, color: AppColors.textMuted)),
              const SizedBox(height: 8),
              ...s.setupPerformance.map((p) => _SetupPerfTile(row: p)),
            ],
            const SizedBox(height: 20),
            const Text('Today\'s trades only', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.text)),
            const SizedBox(height: 8),
            _RecentTradesList(),
          ],
        ),
        loading: () => const Center(child: CircularProgressIndicator(color: AppColors.accent)),
        error: (e, _) => Center(child: Text('Error: $e', style: const TextStyle(color: AppColors.loss))),
      ),
    );
  }
}

class _DailyPnlTile extends StatelessWidget {
  final DailyPnlRow row;
  const _DailyPnlTile({required this.row});

  @override
  Widget build(BuildContext context) {
    final color = row.netPnlInr >= 0 ? AppColors.profit : AppColors.loss;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(color: AppColors.card, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppColors.border)),
      child: Row(
        children: [
          Text(row.date, style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.text)),
          const Spacer(),
          Text(
            '${row.netPnlInr >= 0 ? '+' : ''}₹${row.netPnlInr.toStringAsFixed(0)}',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: color),
          ),
        ],
      ),
    );
  }
}

class _SetupPerfTile extends StatelessWidget {
  final SetupPerformanceRow row;
  const _SetupPerfTile({required this.row});

  @override
  Widget build(BuildContext context) {
    final color = row.netPnlInr >= 0 ? AppColors.profit : AppColors.loss;
    final badge = row.tier == 'high' ? 'TOP' : (row.tier == 'low' ? 'LOW' : 'MID');
    final badgeColor = row.tier == 'high' ? AppColors.profit : (row.tier == 'low' ? AppColors.loss : AppColors.textMuted);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: badgeColor.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(child: Text(row.label, style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.text, fontSize: 13))),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(color: badgeColor.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(4)),
                      child: Text(badge, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, color: badgeColor)),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text('${row.wins}W / ${row.losses}L · ${row.winRatePct.toStringAsFixed(0)}% win · ${row.totalTrades} trades', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text('₹${row.netPnlInr.toStringAsFixed(0)}', style: TextStyle(fontWeight: FontWeight.w800, color: color, fontSize: 14)),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final String sub;
  final Color color;
  const _StatCard({required this.title, required this.value, required this.sub, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppColors.card, borderRadius: BorderRadius.circular(14), border: Border.all(color: AppColors.border)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
          const SizedBox(height: 6),
          Text(value, style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: color)),
          Text(sub, style: const TextStyle(fontSize: 12, color: AppColors.textMuted)),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  final bool fullWidth;
  const _MiniStat({required this.label, required this.value, required this.color, this.fullWidth = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: fullWidth ? double.infinity : null,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.card, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: color)),
        ],
      ),
    );
  }
}

class _RecentTradesList extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(tradeHistoryProvider);
    return history.when(
      data: (data) {
        final items = (data['today_trades'] as List? ?? data['items'] as List? ?? [])
            .take(10)
            .map((e) => TradeRecord.fromJson(e as Map<String, dynamic>))
            .toList();
        if (items.isEmpty) {
          return const Text('No trades yet', style: TextStyle(color: AppColors.textMuted));
        }
        return Column(
          children: items.map((t) => _TradeTile(trade: t)).toList(),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }
}

class _TradeTile extends StatelessWidget {
  final TradeRecord trade;
  const _TradeTile({required this.trade});

  Color get _statusColor => switch (trade.status) {
        'WIN' => AppColors.profit,
        'LOSS' => AppColors.loss,
        'OPEN' => AppColors.accent,
        _ => AppColors.textMuted,
      };

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: AppColors.card, borderRadius: BorderRadius.circular(10), border: Border.all(color: AppColors.border)),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${trade.direction} ${trade.symbol}', style: const TextStyle(fontWeight: FontWeight.w700, color: AppColors.text, fontSize: 13)),
                Text('${trade.setup} · ${trade.leverage}x · ${trade.status}', style: TextStyle(fontSize: 11, color: _statusColor)),
              ],
            ),
          ),
          Text(
            trade.status == 'OPEN' ? 'OPEN' : '₹${trade.pnlInr.toStringAsFixed(0)}',
            style: TextStyle(fontWeight: FontWeight.w700, color: _statusColor, fontSize: 13),
          ),
        ],
      ),
    );
  }
}
