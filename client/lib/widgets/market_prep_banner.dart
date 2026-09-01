import 'package:flutter/material.dart';

import '../models/market_prep.dart';
import '../theme/app_theme.dart';
import '../utils/price_format.dart';

class MarketPrepBanner extends StatelessWidget {
  final MarketPrep prep;

  const MarketPrepBanner({super.key, required this.prep});

  Color _trendColor(String t) => t == 'up' ? AppColors.profit : (t == 'down' ? AppColors.loss : AppColors.textMuted);

  @override
  Widget build(BuildContext context) {
    final macro = prep.macro;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.accentBlue.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('MARKET PREP + NEWS DIGEST', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.accentBlue, letterSpacing: 1)),
          const SizedBox(height: 8),
          Text(prep.headline, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.text, height: 1.35)),
          if (macro.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              'BTC dom ${macro['btc_dominance_pct']}% · MCap \$${macro['total_market_cap_usd']}T · Fear & Greed ${macro['fear_greed_index']} (${macro['fear_greed_label']})',
              style: const TextStyle(fontSize: 10, color: AppColors.gold, height: 1.3),
            ),
          ],
          const SizedBox(height: 10),
          ...prep.pairs.map((p) => Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    SizedBox(width: 42, child: Text(p.label, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.gold))),
                    Expanded(child: Text(formatPrice(p.price), style: const TextStyle(fontSize: 11, color: AppColors.text))),
                    Text('${p.changePct24h >= 0 ? '+' : ''}${p.changePct24h.toStringAsFixed(1)}%', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: _trendColor(p.trend))),
                    const SizedBox(width: 6),
                    Text('Fund ${p.fundingPct >= 0 ? '+' : ''}${p.fundingPct.toStringAsFixed(3)}%', style: const TextStyle(fontSize: 9, color: AppColors.textMuted)),
                  ],
                ),
              )),
          if (prep.liquidationLandscape.isNotEmpty) ...[
            const Divider(height: 14, color: AppColors.border),
            const Text('LIQ LANDSCAPE', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.textMuted)),
            ...prep.liquidationLandscape.map((l) => Text(
                  '${l['label']}: above ${formatPrice((l['above'] as num?)?.toDouble() ?? 0)} · below ${formatPrice((l['below'] as num?)?.toDouble() ?? 0)}',
                  style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
                )),
          ],
          if (prep.watchlist.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('WATCHLIST', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.textMuted)),
            ...prep.watchlist.map((w) => Text('• ${w['pair']}: ${w['note']}', style: const TextStyle(fontSize: 10, color: AppColors.accentBlue))),
          ],
          if (prep.topNews.isNotEmpty) ...[
            const Divider(height: 14, color: AppColors.border),
            ...prep.topNews.take(3).map((n) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text('• ${n['title']} · ${n['sentiment']} · ${n['impact']}', style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.3), maxLines: 2, overflow: TextOverflow.ellipsis),
                )),
          ],
          const SizedBox(height: 6),
          Text(prep.disclaimer, style: TextStyle(fontSize: 9, color: AppColors.textMuted.withValues(alpha: 0.7), height: 1.3)),
        ],
      ),
    );
  }
}
