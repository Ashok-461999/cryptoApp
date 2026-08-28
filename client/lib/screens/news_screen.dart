import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../providers/providers.dart';
import '../theme/app_theme.dart';

class NewsScreen extends ConsumerStatefulWidget {
  const NewsScreen({super.key});

  @override
  ConsumerState<NewsScreen> createState() => _NewsScreenState();
}

class _NewsScreenState extends ConsumerState<NewsScreen> {
  Timer? _timer;
  String _filter = 'ALL';

  static const _filters = ['ALL', 'BTC', 'GOLD', 'MEME', 'MACRO', 'GLOBAL'];

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(minutes: 2), (_) => ref.invalidate(marketNewsProvider));
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  List<Map<String, dynamic>> _filtered(List<Map<String, dynamic>> items) {
    if (_filter == 'ALL') return items;
    return items.where((item) {
      final markets = (item['affected_markets'] as List? ?? []).map((e) => '$e').toList();
      return markets.contains(_filter);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final news = ref.watch(marketNewsProvider);

    return RefreshIndicator(
      color: AppColors.accent,
      onRefresh: () async {
        ref.invalidate(marketNewsProvider);
        await ref.read(marketNewsProvider.future);
      },
      child: news.when(
        data: (data) {
          final summary = data['summary'] as Map<String, dynamic>? ?? {};
          final allItems = (data['items'] as List? ?? []).cast<Map<String, dynamic>>();
          final items = _filtered(allItems);
          final mood = summary['market_mood'] ?? 'neutral';
          final moodColor = mood == 'bullish' ? AppColors.profit : (mood == 'bearish' ? AppColors.loss : AppColors.textMuted);
          final topMarkets = (summary['top_affected_markets'] as List? ?? []).cast<String>();
          final fetchedAt = data['fetched_at']?.toString() ?? '';
          String liveLabel = 'Live';
          try {
            if (fetchedAt.isNotEmpty) {
              final dt = DateTime.parse(fetchedAt).toLocal();
              liveLabel = 'Live · ${DateFormat('HH:mm').format(dt)}';
            }
          } catch (_) {}

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Text('Global Live News', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.text)),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.profit.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppColors.profit.withValues(alpha: 0.4)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(width: 6, height: 6, decoration: const BoxDecoration(color: AppColors.profit, shape: BoxShape.circle)),
                        const SizedBox(width: 5),
                        Text(liveLabel, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.profit)),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              const Text('Crypto + macro headlines · see which markets move (BTC, Gold, Meme…)', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
              const SizedBox(height: 16),
              PremiumCard(
                highlight: true,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text('MARKET MOOD: ${mood.toString().toUpperCase()}', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: moodColor, letterSpacing: 1)),
                        const Spacer(),
                        Text('${summary['total_headlines'] ?? allItems.length} headlines', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(child: _SentimentBar(label: 'Bullish', pct: summary['bullish_count'] ?? 0, total: allItems.length, color: AppColors.profit)),
                        const SizedBox(width: 12),
                        Expanded(child: _SentimentBar(label: 'Bearish', pct: summary['bearish_count'] ?? 0, total: allItems.length, color: AppColors.loss)),
                      ],
                    ),
                    if (topMarkets.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      const Text('MOST AFFECTED NOW', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1)),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: topMarkets.take(8).map((m) => _MarketChip(label: m, highlight: true)).toList(),
                      ),
                    ],
                    const SizedBox(height: 12),
                    Text(
                      summary['market_reaction'] ?? 'Watch chart setups — news is context only.',
                      style: const TextStyle(fontSize: 12, color: AppColors.text, height: 1.45),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: _filters.map((f) {
                    final on = _filter == f;
                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: FilterChip(
                        label: Text(f, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: on ? AppColors.bg : AppColors.textMuted)),
                        selected: on,
                        onSelected: (_) => setState(() => _filter = f),
                        selectedColor: AppColors.accent,
                        backgroundColor: AppColors.card,
                        side: BorderSide(color: on ? AppColors.accent : AppColors.border),
                        showCheckmark: false,
                      ),
                    );
                  }).toList(),
                ),
              ),
              const SizedBox(height: 12),
              Text('Showing ${items.length} · filter: $_filter', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
              const SizedBox(height: 8),
              if (items.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(child: Text('No headlines for this filter — try ALL', style: TextStyle(color: AppColors.textMuted))),
                )
              else
                ...items.map((item) => _NewsCard(item: item)),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator(color: AppColors.accent)),
        error: (e, _) => Center(child: Text('News unavailable — check backend\n$e', textAlign: TextAlign.center, style: const TextStyle(color: AppColors.loss))),
      ),
    );
  }
}

class _SentimentBar extends StatelessWidget {
  final String label;
  final int pct;
  final int total;
  final Color color;
  const _SentimentBar({required this.label, required this.pct, required this.total, required this.color});

  @override
  Widget build(BuildContext context) {
    final frac = total > 0 ? pct / total : 0.0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('$label $pct', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: color)),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(value: frac, minHeight: 6, backgroundColor: AppColors.border, color: color),
        ),
      ],
    );
  }
}

class _MarketChip extends StatelessWidget {
  final String label;
  final bool highlight;
  const _MarketChip({required this.label, this.highlight = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: (highlight ? AppColors.accent : AppColors.bgElevated).withValues(alpha: highlight ? 0.2 : 1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: highlight ? AppColors.accent.withValues(alpha: 0.5) : AppColors.border),
      ),
      child: Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: highlight ? AppColors.accent : AppColors.textMuted)),
    );
  }
}

class _NewsCard extends StatelessWidget {
  final Map<String, dynamic> item;
  const _NewsCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final sent = item['sentiment'] ?? 'neutral';
    final color = sent == 'bullish' ? AppColors.profit : (sent == 'bearish' ? AppColors.loss : AppColors.textMuted);
    final published = item['published_at']?.toString() ?? '';
    final markets = (item['affected_markets'] as List? ?? []).map((e) => '$e').toList();
    String timeLabel = published;
    try {
      final dt = DateTime.parse(published);
      timeLabel = DateFormat('MMM d, HH:mm').format(dt.toLocal());
    } catch (_) {}

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(6)),
                child: Text(sent.toString().toUpperCase(), style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: color)),
              ),
              const SizedBox(width: 8),
              Expanded(child: Text(item['source'] ?? '', style: const TextStyle(fontSize: 10, color: AppColors.textMuted))),
              Text(timeLabel, style: const TextStyle(fontSize: 9, color: AppColors.textMuted)),
            ],
          ),
          const SizedBox(height: 8),
          Text(item['title'] ?? '', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.text, height: 1.3)),
          if (markets.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('MARKETS AFFECTED', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.accentBlue, letterSpacing: 0.5)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: markets.map((m) => _MarketChip(label: m)).toList(),
            ),
          ],
          if (item['market_impact'] != null) ...[
            const SizedBox(height: 8),
            Text(item['market_impact'], style: const TextStyle(fontSize: 11, color: AppColors.accent, height: 1.35)),
          ],
          if (item['reaction'] != null) ...[
            const SizedBox(height: 6),
            Text(item['reaction'], style: TextStyle(fontSize: 11, color: color.withValues(alpha: 0.9), height: 1.35)),
          ],
        ],
      ),
    );
  }
}
