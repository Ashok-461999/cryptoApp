import 'package:flutter/material.dart';

import '../models/market_prep.dart';
import '../theme/app_theme.dart';
import '../utils/price_format.dart';

/// Section 11 major pairs strip for Markets tab — funding, trend, liq levels.
class AlphaMarketsPanel extends StatelessWidget {
  final MarketPrep prep;

  const AlphaMarketsPanel({super.key, required this.prep});

  Color _trendColor(String t) =>
      t == 'up' ? AppColors.profit : (t == 'down' ? AppColors.loss : AppColors.textMuted);

  IconData _trendIcon(String t) =>
      t == 'up' ? Icons.trending_up : (t == 'down' ? Icons.trending_down : Icons.trending_flat);

  @override
  Widget build(BuildContext context) {
    final macro = prep.macro;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.gold.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'DELTA × BINANCE ALPHA — MAJOR PAIRS',
            style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.gold, letterSpacing: 0.8),
          ),
          if (macro.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              'BTC.D ${macro['btc_dominance_pct']}% · MCap \$${macro['total_market_cap_usd']}T · F&G ${macro['fear_greed_index']}',
              style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
            ),
          ],
          const SizedBox(height: 12),
          ...prep.pairs.map((p) {
            final oiLabel = p.oiUsdt >= 1e9
                ? '\$${(p.oiUsdt / 1e9).toStringAsFixed(2)}B'
                : '\$${(p.oiUsdt / 1e6).toStringAsFixed(0)}M';
            return Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 44,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(p.label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppColors.text)),
                        Icon(_trendIcon(p.trend), size: 14, color: _trendColor(p.trend)),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(formatPrice(p.price), style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.text)),
                            const SizedBox(width: 8),
                            Text(
                              '${p.changePct24h >= 0 ? '+' : ''}${p.changePct24h.toStringAsFixed(1)}%',
                              style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: _trendColor(p.trend)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Fund ${p.fundingPct >= 0 ? '+' : ''}${p.fundingPct.toStringAsFixed(3)}% · OI $oiLabel',
                          style: const TextStyle(fontSize: 9, color: AppColors.accentBlue),
                        ),
                        Text(
                          'Liq ↑ ${formatPrice(p.liqAbove)} · ↓ ${formatPrice(p.liqBelow)}',
                          style: const TextStyle(fontSize: 9, color: AppColors.textMuted),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
          if (prep.watchlist.isNotEmpty) ...[
            const Divider(height: 16, color: AppColors.border),
            const Text('WATCHLIST', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.textMuted)),
            const SizedBox(height: 4),
            ...prep.watchlist.take(3).map(
                  (w) => Text('• ${w['pair']}: ${w['note']}', style: const TextStyle(fontSize: 10, color: AppColors.accentBlue)),
                ),
          ],
        ],
      ),
    );
  }
}
