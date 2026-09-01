import 'package:flutter/material.dart';

import '../models/market_prep.dart';
import '../theme/app_theme.dart';
import '../utils/price_format.dart';

class MarketPrepBanner extends StatelessWidget {
  final MarketPrep prep;
  final bool compact;
  final VoidCallback? onToggle;

  const MarketPrepBanner({
    super.key,
    required this.prep,
    this.compact = true,
    this.onToggle,
  });

  Color _trendColor(String t) => t == 'up' ? AppColors.profit : (t == 'down' ? AppColors.loss : AppColors.textMuted);

  @override
  Widget build(BuildContext context) {
    final macro = prep.macro;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.accentBlue.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('MARKET PREP', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.accentBlue, letterSpacing: 0.8)),
              ),
              if (onToggle != null)
                GestureDetector(
                  onTap: onToggle,
                  child: Icon(compact ? Icons.expand_more : Icons.expand_less, size: 18, color: AppColors.accent),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(prep.headline, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.text, height: 1.3), maxLines: compact ? 2 : null),
          if (!compact) ...[
            if (macro.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'BTC.D ${macro['btc_dominance_pct']}% · F&G ${macro['fear_greed_index']} (${macro['fear_greed_label']})',
                style: const TextStyle(fontSize: 10, color: AppColors.gold),
              ),
            ],
            const SizedBox(height: 8),
            ...prep.pairs.map((p) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    children: [
                      SizedBox(width: 40, child: Text(p.label, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.gold))),
                      Expanded(child: Text(formatPrice(p.price), style: const TextStyle(fontSize: 10, color: AppColors.text))),
                      Text('${p.changePct24h >= 0 ? '+' : ''}${p.changePct24h.toStringAsFixed(1)}%', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: _trendColor(p.trend))),
                      const SizedBox(width: 6),
                      Text('Fund ${p.fundingPct >= 0 ? '+' : ''}${p.fundingPct.toStringAsFixed(3)}%', style: const TextStyle(fontSize: 9, color: AppColors.textMuted)),
                    ],
                  ),
                )),
            if (prep.topNews.isNotEmpty) ...[
              const Divider(height: 12, color: AppColors.border),
              ...prep.topNews.take(2).map((n) => Text('• ${n['title']}', style: const TextStyle(fontSize: 9, color: AppColors.textMuted), maxLines: 1, overflow: TextOverflow.ellipsis)),
            ],
          ],
        ],
      ),
    );
  }
}
