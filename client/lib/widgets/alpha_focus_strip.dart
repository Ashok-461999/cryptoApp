import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../utils/price_format.dart';

/// Compact BTC & Gold strip — no charts, instant render from WS snapshot.
class AlphaFocusStrip extends StatelessWidget {
  final List<Map<String, dynamic>> items;
  final void Function(Map<String, dynamic> item)? onTap;

  const AlphaFocusStrip({super.key, required this.items, this.onTap});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();

    return SizedBox(
      height: 118,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (ctx, i) => _StripCard(item: items[i], onTap: onTap),
      ),
    );
  }
}

class _StripCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final void Function(Map<String, dynamic> item)? onTap;

  const _StripCard({required this.item, this.onTap});

  Color _predColor(String p) =>
      p == 'bullish' ? AppColors.profit : (p == 'bearish' ? AppColors.loss : AppColors.textMuted);

  double? _d(dynamic v) => v is num ? v.toDouble() : double.tryParse('$v');

  @override
  Widget build(BuildContext context) {
    final base = item['base']?.toString() ?? '';
    final icon = item['icon']?.toString() ?? '🪙';
    final prediction = item['prediction']?.toString() ?? 'neutral';
    final action = item['action']?.toString() ?? 'WAIT';
    final color = _predColor(prediction);
    final price = (item['last_price'] as num?)?.toDouble() ?? 0;
    final change = (item['change_pct_24h'] as num?)?.toDouble() ?? 0;
    final chart = item['chart'] as Map<String, dynamic>? ?? {};
    final entry = _d(chart['strategy_line']) ?? _d(chart['entry']);
    final sl = _d(chart['stop_loss']);
    final tp = _d(chart['target']);
    final deriv = item['derivatives'] as Map<String, dynamic>? ?? {};
    final funding = (deriv['funding_pct_8h'] as num?)?.toDouble();

    return GestureDetector(
      onTap: onTap == null ? null : () => onTap!(item),
      child: Container(
        width: 168,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.35)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(icon, style: const TextStyle(fontSize: 16)),
                const SizedBox(width: 6),
                Text(base, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppColors.text)),
                const Spacer(),
                Text(
                  '${change >= 0 ? '+' : ''}${change.toStringAsFixed(1)}%',
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: color),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(formatPrice(price), style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.text)),
            const SizedBox(height: 6),
            Text(
              '$action · ${prediction.toUpperCase()}',
              style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: color, letterSpacing: 0.3),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const Spacer(),
            if (entry != null && sl != null && tp != null)
              Text(
                'E ${formatPrice(entry)} · SL ${formatPrice(sl)} · TP ${formatPrice(tp)}',
                style: const TextStyle(fontSize: 8, color: AppColors.textMuted, height: 1.2),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            if (funding != null)
              Text(
                'Fund ${funding >= 0 ? '+' : ''}${funding.toStringAsFixed(3)}%',
                style: const TextStyle(fontSize: 8, color: AppColors.accentBlue),
              ),
          ],
        ),
      ),
    );
  }
}
