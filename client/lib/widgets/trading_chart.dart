import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Binance-style candlestick chart with S/R, strategy line, expected move zone + pinch/zoom.
class TradingChart extends StatefulWidget {
  final List<Map<String, dynamic>> candles;
  final double? entry;
  final double? stopLoss;
  final double? target;
  final double? support;
  final double? resistance;
  final double? strategyLine;
  final double? expectedMoveLow;
  final double? expectedMoveHigh;
  final String? prediction;
  final String interval;
  final bool loading;

  const TradingChart({
    super.key,
    required this.candles,
    this.entry,
    this.stopLoss,
    this.target,
    this.support,
    this.resistance,
    this.strategyLine,
    this.expectedMoveLow,
    this.expectedMoveHigh,
    this.prediction,
    this.interval = '5m',
    this.loading = false,
  });

  @override
  State<TradingChart> createState() => _TradingChartState();
}

class _TradingChartState extends State<TradingChart> {
  double _zoom = 1.0;
  static const _minZoom = 0.6;
  static const _maxZoom = 4.0;

  void _zoomIn() => setState(() => _zoom = (_zoom * 1.25).clamp(_minZoom, _maxZoom));
  void _zoomOut() => setState(() => _zoom = (_zoom / 1.25).clamp(_minZoom, _maxZoom));
  void _resetZoom() => setState(() => _zoom = 1.0);

  List<Map<String, dynamic>> get _visibleCandles {
    if (widget.candles.isEmpty) return widget.candles;
    final count = (widget.candles.length / _zoom).round().clamp(15, widget.candles.length);
    return widget.candles.sublist(widget.candles.length - count);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.loading) {
      return const SizedBox(height: 320, child: Center(child: CircularProgressIndicator(color: AppColors.accent)));
    }
    if (widget.candles.length < 3) {
      return const SizedBox(
        height: 320,
        child: Center(child: Text('No chart data', style: TextStyle(color: AppColors.textMuted))),
      );
    }

    final visible = _visibleCandles;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Row(
            children: [
              Expanded(
                child: Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    Text('Chart · ${widget.interval}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.accent)),
                    if (widget.support != null) const _LegendDot(color: AppColors.profit, label: 'Support'),
                    if (widget.resistance != null) const _LegendDot(color: AppColors.loss, label: 'Resistance'),
                    if (widget.entry != null) const _LegendDot(color: AppColors.accent, label: 'Entry'),
                    if (widget.stopLoss != null) const _LegendDot(color: AppColors.loss, label: 'SL'),
                    if (widget.target != null) const _LegendDot(color: AppColors.profit, label: 'T1'),
                  ],
                ),
              ),
              _ZoomBtn(icon: Icons.remove, onTap: _zoomOut),
              const SizedBox(width: 4),
              Text('${(_zoom * 100).round()}%', style: const TextStyle(fontSize: 10, color: AppColors.textMuted, fontWeight: FontWeight.w700)),
              const SizedBox(width: 4),
              _ZoomBtn(icon: Icons.add, onTap: _zoomIn),
              const SizedBox(width: 4),
              _ZoomBtn(icon: Icons.fit_screen, onTap: _resetZoom, small: true),
            ],
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 300,
          child: InteractiveViewer(
            minScale: 0.8,
            maxScale: 3.0,
            panEnabled: _zoom > 1.0,
            child: CustomPaint(
              size: Size.infinite,
              painter: _CandlePainter(
                candles: visible,
                entry: widget.entry,
                stopLoss: widget.stopLoss,
                target: widget.target,
                support: widget.support,
                resistance: widget.resistance,
                strategyLine: widget.strategyLine,
                expectedMoveLow: widget.expectedMoveLow,
                expectedMoveHigh: widget.expectedMoveHigh,
                prediction: widget.prediction,
              ),
              child: Container(),
            ),
          ),
        ),
      ],
    );
  }
}

class _ZoomBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  final bool small;

  const _ZoomBtn({required this.icon, required this.onTap, this.small = false});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: EdgeInsets.all(small ? 4 : 6),
        decoration: BoxDecoration(
          color: AppColors.bgElevated,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: AppColors.border),
        ),
        child: Icon(icon, size: small ? 14 : 16, color: AppColors.accent),
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(fontSize: 9, color: color)),
      ],
    );
  }
}

class _CandlePainter extends CustomPainter {
  final List<Map<String, dynamic>> candles;
  final double? entry;
  final double? stopLoss;
  final double? target;
  final double? support;
  final double? resistance;
  final double? strategyLine;
  final double? expectedMoveLow;
  final double? expectedMoveHigh;
  final String? prediction;

  _CandlePainter({
    required this.candles,
    this.entry,
    this.stopLoss,
    this.target,
    this.support,
    this.resistance,
    this.strategyLine,
    this.expectedMoveLow,
    this.expectedMoveHigh,
    this.prediction,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final lows = candles.map((c) => (c['low'] as num).toDouble()).toList();
    final highs = candles.map((c) => (c['high'] as num).toDouble()).toList();
    var minY = lows.reduce(math.min);
    var maxY = highs.reduce(math.max);
    for (final p in [entry, stopLoss, target, support, resistance, strategyLine, expectedMoveLow, expectedMoveHigh]) {
      if (p != null && p > 0) {
        minY = math.min(minY, p);
        maxY = math.max(maxY, p);
      }
    }
    final pad = (maxY - minY) * 0.08;
    minY -= pad;
    maxY += pad;
    final range = maxY - minY;
    if (range <= 0) return;

    double yOf(double price) => size.height - ((price - minY) / range) * size.height;

    if (expectedMoveLow != null && expectedMoveHigh != null && expectedMoveLow! > 0 && expectedMoveHigh! > 0) {
      final top = yOf(math.max(expectedMoveLow!, expectedMoveHigh!));
      final bottom = yOf(math.min(expectedMoveLow!, expectedMoveHigh!));
      final zoneColor = prediction == 'bearish'
          ? AppColors.loss.withValues(alpha: 0.12)
          : AppColors.profit.withValues(alpha: 0.12);
      canvas.drawRect(Rect.fromLTRB(0, top, size.width, bottom), Paint()..color = zoneColor);
    }

    final gridPaint = Paint()..color = AppColors.border.withValues(alpha: 0.35);
    for (var i = 1; i < 4; i++) {
      final y = size.height * i / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final candleW = size.width / candles.length;
    final bodyW = math.max(2.0, candleW * 0.55);

    for (var i = 0; i < candles.length; i++) {
      final c = candles[i];
      final o = (c['open'] as num).toDouble();
      final h = (c['high'] as num).toDouble();
      final l = (c['low'] as num).toDouble();
      final cl = (c['close'] as num).toDouble();
      final bull = cl >= o;
      final color = bull ? AppColors.profit : AppColors.loss;
      final x = i * candleW + candleW / 2;

      final wick = Paint()..color = color..strokeWidth = 1;
      canvas.drawLine(Offset(x, yOf(h)), Offset(x, yOf(l)), wick);

      final top = yOf(math.max(o, cl));
      final bottom = yOf(math.min(o, cl));
      final rect = Rect.fromCenter(center: Offset(x, (top + bottom) / 2), width: bodyW, height: math.max(1.5, bottom - top));
      canvas.drawRect(rect, Paint()..color = color);
    }

    final levels = <_ChartLevel>[];
    void addLevel(double? price, Color color, String label, {bool dashed = true}) {
      if (price == null || price <= 0) return;
      levels.add(_ChartLevel(price: price, color: color, label: label, dashed: dashed));
    }

    addLevel(support, AppColors.profit, 'Sup', dashed: false);
    addLevel(resistance, AppColors.loss, 'Res', dashed: false);
    addLevel(strategyLine, AppColors.accentBlue, 'Strategy');
    addLevel(entry, AppColors.accent, 'Entry');
    addLevel(stopLoss, AppColors.loss, 'SL');
    addLevel(target, AppColors.profit, 'T1');

    final merged = _mergeCloseLevels(levels, range * 0.0015);
    merged.sort((a, b) => yOf(b.price).compareTo(yOf(a.price)));

    const minGap = 14.0;
    const labelH = 12.0;
    final placedYs = <double>[];
    final labelLayouts = <({_ChartLevel level, double lineY, double labelY, TextPainter tp})>[];

    for (final lv in merged) {
      final lineY = yOf(lv.price);
      var labelY = lineY - labelH / 2;
      labelY = labelY.clamp(2.0, size.height - labelH - 2);
      for (final py in placedYs) {
        if ((labelY - py).abs() < minGap) {
          labelY = py + minGap;
        }
      }
      labelY = labelY.clamp(2.0, size.height - labelH - 2);
      placedYs.add(labelY);

      final tp = TextPainter(
        text: TextSpan(
          text: '${lv.label} ${_fmt(lv.price)}',
          style: TextStyle(color: lv.color, fontSize: 9, fontWeight: FontWeight.w700),
        ),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: size.width * 0.42);

      labelLayouts.add((level: lv, lineY: lineY, labelY: labelY, tp: tp));
    }

    for (final item in labelLayouts) {
      final lv = item.level;
      final paint = Paint()..color = lv.color..strokeWidth = lv.dashed ? 1.2 : 1.6;
      final y = item.lineY;
      if (lv.dashed) {
        const dash = 6.0;
        var x = 0.0;
        while (x < size.width) {
          canvas.drawLine(Offset(x, y), Offset(math.min(x + dash, size.width), y), paint);
          x += dash * 2;
        }
      } else {
        canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
      }
    }

    for (final item in labelLayouts) {
      final tp = item.tp;
      final x = size.width - tp.width - 6;
      final y = item.labelY;
      final bg = RRect.fromRectAndRadius(
        Rect.fromLTWH(x - 3, y - 1, tp.width + 6, tp.height + 2),
        const Radius.circular(3),
      );
      canvas.drawRRect(bg, Paint()..color = AppColors.bg.withValues(alpha: 0.88));
      tp.paint(canvas, Offset(x, y));
    }

    if (prediction != null && prediction!.isNotEmpty) {
      final arrow = prediction == 'bullish' ? '↑ BULL' : (prediction == 'bearish' ? '↓ BEAR' : '↔');
      final tp = TextPainter(
        text: TextSpan(text: arrow, style: TextStyle(color: AppColors.gold, fontSize: 11, fontWeight: FontWeight.w800)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(size.width - tp.width - 8, 8));
    }
  }

  String _fmt(double price) => price >= 1000 ? price.toStringAsFixed(2) : price.toStringAsFixed(4);

  List<_ChartLevel> _mergeCloseLevels(List<_ChartLevel> levels, double threshold) {
    if (levels.isEmpty) return levels;
    final sorted = [...levels]..sort((a, b) => a.price.compareTo(b.price));
    final out = <_ChartLevel>[];
    var bucket = sorted.first;
    for (var i = 1; i < sorted.length; i++) {
      final lv = sorted[i];
      if ((lv.price - bucket.price).abs() <= threshold) {
        bucket = _ChartLevel(
          price: (bucket.price + lv.price) / 2,
          color: bucket.color,
          label: '${bucket.label}/${lv.label}',
          dashed: bucket.dashed && lv.dashed,
        );
      } else {
        out.add(bucket);
        bucket = lv;
      }
    }
    out.add(bucket);
    return out;
  }

  @override
  bool shouldRepaint(covariant _CandlePainter old) =>
      old.candles != candles ||
      old.entry != entry ||
      old.stopLoss != stopLoss ||
      old.target != target ||
      old.support != support ||
      old.resistance != resistance ||
      old.strategyLine != strategyLine;
}

class _ChartLevel {
  final double price;
  final Color color;
  final String label;
  final bool dashed;

  const _ChartLevel({
    required this.price,
    required this.color,
    required this.label,
    this.dashed = true,
  });
}

/// Timeframe chips for chart — scalp + structure intervals.
class ChartTimeframeBar extends StatelessWidget {
  final String selected;
  final ValueChanged<String> onSelected;

  static const intervals = ['1s', '5s', '10s', '1m', '3m', '5m', '15m'];

  const ChartTimeframeBar({super.key, required this.selected, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: intervals.map((iv) {
          final on = selected == iv;
          final scalp = iv.endsWith('s');
          return Padding(
            padding: const EdgeInsets.only(right: 6),
            child: InkWell(
              onTap: () => onSelected(iv),
              borderRadius: BorderRadius.circular(8),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: on ? AppColors.accent.withValues(alpha: 0.2) : AppColors.bgElevated,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: on ? AppColors.accent : AppColors.border),
                ),
                child: Text(
                  iv.toUpperCase(),
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: on ? AppColors.accent : (scalp ? AppColors.gold : AppColors.textMuted),
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
