import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/crypto_signal.dart';
import '../providers/live_signals_provider.dart';
import '../providers/providers.dart';
import '../screens/signal_chart_screen.dart';
import '../widgets/alpha_focus_strip.dart';
import '../widgets/delta_signal_card.dart';
import '../widgets/market_prep_banner.dart';
import '../theme/app_theme.dart';

class SignalsScreen extends ConsumerStatefulWidget {
  const SignalsScreen({super.key});

  @override
  ConsumerState<SignalsScreen> createState() => _SignalsScreenState();
}

enum _CategoryFilter { all, top, btcGold, majors, meme, alts }

class _SignalsScreenState extends ConsumerState<SignalsScreen> {
  _CategoryFilter _filter = _CategoryFilter.all;
  bool _prepExpanded = false;

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

  String _sessionLabel() {
    final h = DateTime.now().toUtc().hour;
    if (h >= 13 && h < 16) return 'NY Open';
    if (h >= 7 && h < 9) return 'London';
    if (h >= 0 && h < 2) return 'Asia';
    if (h >= 18 && h < 20) return 'US Afternoon';
    return 'Overnight';
  }

  @override
  Widget build(BuildContext context) {
    final live = ref.watch(liveSignalsProvider);
    final tradingCfg = ref.watch(tradingSettingsProvider).valueOrNull;
    final filtered = List<CryptoSignal>.from(_applyFilter(live.signals))
      ..sort((a, b) {
        final as = a.confluenceScore > 0 ? a.confluenceScore : a.confidence;
        final bs = b.confluenceScore > 0 ? b.confluenceScore : b.confidence;
        if (as != bs) return bs.compareTo(as);
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
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Delta × Binance Alpha', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: AppColors.text)),
                        const SizedBox(height: 2),
                        Text('${_sessionLabel()} · Confluence 70+ · ${live.takeCountToday}/${live.takeCapLabel} today', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                      ],
                    ),
                  ),
                  _LiveBadge(connected: live.connected),
                ],
              ),
            ),
          ),
          if (live.focusTracker.isNotEmpty)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: AlphaFocusStrip(
                  items: live.focusTracker,
                  onTap: (item) => openSymbolChart(context, item['symbol']?.toString() ?? '', tracker: item),
                ),
              ),
            ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
              child: _StatusBar(live: live, tradingConfig: tradingCfg),
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
                  child: Text(live.error!, style: const TextStyle(fontSize: 11, color: AppColors.loss)),
                ),
              ),
            ),
          if (live.marketPrep != null && live.signals.length < 5)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: MarketPrepBanner(prep: live.marketPrep!, compact: !_prepExpanded, onToggle: () => setState(() => _prepExpanded = !_prepExpanded)),
              ),
            ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
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
                  'No signals ≥70 confluence yet\nScanning ${live.totalScanned} pairs',
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
                  child: DeltaSignalCard(
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
          Container(width: 7, height: 7, decoration: BoxDecoration(color: connected ? AppColors.profit : AppColors.textMuted, shape: BoxShape.circle)),
          const SizedBox(width: 6),
          Text(connected ? 'LIVE' : 'OFF', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: connected ? AppColors.profit : AppColors.textMuted)),
        ],
      ),
    );
  }
}

class _StatusBar extends StatelessWidget {
  final LiveSignalsState live;
  final Map<String, dynamic>? tradingConfig;
  const _StatusBar({required this.live, this.tradingConfig});

  @override
  Widget build(BuildContext context) {
    final cfg = tradingConfig;
    final paused = cfg?['trading_paused'] == true;
    final status = cfg?['status_label'] ?? (paused ? 'PAUSED' : (cfg != null ? 'RUNNING' : '—'));

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Icon(paused ? Icons.pause_circle : Icons.bolt, size: 16, color: paused ? AppColors.warn : AppColors.profit),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Engine $status · ${live.totalScanned} scanned', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.text)),
                if (live.lastClosedMessage != null)
                  Text(live.lastClosedMessage!, style: const TextStyle(fontSize: 10, color: AppColors.textMuted), maxLines: 1, overflow: TextOverflow.ellipsis),
              ],
            ),
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
