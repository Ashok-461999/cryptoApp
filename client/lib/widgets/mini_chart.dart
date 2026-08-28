import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class MiniScalpChart extends StatelessWidget {
  final List<Map<String, dynamic>> candles;
  final double entry;
  final double stopLoss;
  final double target;
  final String timeframe;

  const MiniScalpChart({
    super.key,
    required this.candles,
    required this.entry,
    required this.stopLoss,
    required this.target,
    required this.timeframe,
  });

  @override
  Widget build(BuildContext context) {
    if (candles.length < 5) {
      return const SizedBox(height: 120, child: Center(child: Text('Loading chart…', style: TextStyle(fontSize: 11, color: AppColors.textMuted))));
    }

    final spots = <FlSpot>[];
    for (var i = 0; i < candles.length; i++) {
      spots.add(FlSpot(i.toDouble(), (candles[i]['close'] as num).toDouble()));
    }

    final prices = spots.map((s) => s.y).toList();
    final minY = ([...prices, stopLoss, target].reduce((a, b) => a < b ? a : b)) * 0.999;
    final maxY = ([...prices, entry, target].reduce((a, b) => a > b ? a : b)) * 1.001;

    return SizedBox(
      height: 130,
      child: LineChart(
            LineChartData(
              minY: minY,
              maxY: maxY,
              gridData: const FlGridData(show: false),
              titlesData: const FlTitlesData(show: false),
              borderData: FlBorderData(show: false),
              lineBarsData: [
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  color: AppColors.accentBlue,
                  barWidth: 2,
                  dotData: const FlDotData(show: false),
                  belowBarData: BarAreaData(show: true, color: AppColors.accentBlue.withValues(alpha: 0.08)),
                ),
              ],
              extraLinesData: ExtraLinesData(
                horizontalLines: [
                  HorizontalLine(y: entry, color: AppColors.accent, strokeWidth: 1, dashArray: [4, 4], label: HorizontalLineLabel(show: true, labelResolver: (_) => 'Entry', style: const TextStyle(fontSize: 9, color: AppColors.accent))),
                  HorizontalLine(y: stopLoss, color: AppColors.loss, strokeWidth: 1, label: HorizontalLineLabel(show: true, labelResolver: (_) => 'SL', style: const TextStyle(fontSize: 9, color: AppColors.loss))),
                  HorizontalLine(y: target, color: AppColors.profit, strokeWidth: 1, label: HorizontalLineLabel(show: true, labelResolver: (_) => 'T1', style: const TextStyle(fontSize: 9, color: AppColors.profit))),
                ],
              ),
            ),
          ),
    );
  }
}
