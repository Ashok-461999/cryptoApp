import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../utils/price_format.dart';

/// Always-visible BTC & Gold bullish/bearish tracker with strategy line + suggestion.
class BtcGoldTracker extends StatelessWidget {
  final List<Map<String, dynamic>> items;
  final void Function(Map<String, dynamic> item)? onTap;

  const BtcGoldTracker({super.key, required this.items, this.onTap});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Text('BTC & GOLD TRACKER', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1)),
            Spacer(),
            Text('Live prediction', style: TextStyle(fontSize: 9, color: AppColors.textMuted)),
          ],
        ),
        const SizedBox(height: 8),
        ...items.map((item) => _FocusTrackerCard(item: item, onTap: onTap == null ? null : () => onTap!(item))),
      ],
    );
  }
}

class _FocusTrackerCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback? onTap;

  const _FocusTrackerCard({required this.item, this.onTap});

  Color _predColor(String p) => p == 'bullish' ? AppColors.profit : (p == 'bearish' ? AppColors.loss : AppColors.textMuted);

  String _predLabel(String p) => p == 'bullish' ? 'BULLISH' : (p == 'bearish' ? 'BEARISH' : 'NEUTRAL');

  @override
  Widget build(BuildContext context) {
    final base = item['base']?.toString() ?? '';
    final icon = item['icon']?.toString() ?? '🪙';
    final prediction = item['prediction']?.toString() ?? 'neutral';
    final action = item['action']?.toString() ?? 'WAIT';
    final color = _predColor(prediction);
    final price = (item['last_price'] as num?)?.toDouble() ?? 0;
    final confidence = item['confidence'] ?? 0;
    final strategy = item['strategy_label']?.toString() ?? 'Market Structure';
    final suggestion = item['suggestion']?.toString() ?? '';
    final structure = item['market_structure']?.toString() ?? '';
    final levels = item['levels'] as Map<String, dynamic>? ?? {};
    final strategyLine = (levels['strategy_line'] as num?)?.toDouble() ?? 0;
    final support = (levels['support'] as num?)?.toDouble() ?? 0;
    final resistance = (levels['resistance'] as num?)?.toDouble() ?? 0;
    final sl = (levels['stop_loss'] as num?)?.toDouble() ?? 0;
    final target = (levels['target'] as num?)?.toDouble() ?? 0;
    final hasLive = item['has_live_signal'] == true;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.45), width: 1.5),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(icon, style: const TextStyle(fontSize: 22)),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('$base / USDT', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: AppColors.text)),
                      Text(formatPrice(price), style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: color.withValues(alpha: 0.5)),
                  ),
                  child: Text(_predLabel(prediction), style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: color)),
                ),
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                  decoration: BoxDecoration(
                    color: AppColors.bgElevated,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Text(action, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: action == 'BUY' ? AppColors.profit : (action == 'SELL' ? AppColors.loss : AppColors.textMuted))),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                _MiniLevel('Strategy', strategy, AppColors.accent),
                const SizedBox(width: 6),
                _MiniLevel('Line', formatPrice(strategyLine), AppColors.accentBlue),
                const SizedBox(width: 6),
                _MiniLevel('Conf', '$confidence%', color),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(child: _MiniLevel('Support', formatPrice(support), AppColors.profit)),
                const SizedBox(width: 6),
                Expanded(child: _MiniLevel('Resist', formatPrice(resistance), AppColors.loss)),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(child: _MiniLevel('SL', formatPrice(sl), AppColors.loss)),
                const SizedBox(width: 6),
                Expanded(child: _MiniLevel('Target', formatPrice(target), AppColors.profit)),
              ],
            ),
            const SizedBox(height: 8),
            Text(suggestion, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color, height: 1.35)),
            const SizedBox(height: 4),
            Text(structure, style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.3)),
            if (hasLive) ...[
              const SizedBox(height: 6),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.profit.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Text('📡 Live setup active — check Signals tab', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: AppColors.profit)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _MiniLevel extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MiniLevel(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: color)),
          Text(value, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: color), overflow: TextOverflow.ellipsis),
        ],
      ),
    );
  }
}
