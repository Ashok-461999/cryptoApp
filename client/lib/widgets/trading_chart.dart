import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Binance-style candlestick chart with S/R, strategy line, pinch/drag pan + zoom.
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
  static const _minVisible = 20;
  static const _priceAxisWidth = 68.0;
  static const _chartHeight = 320.0;

  int _visibleCount = 60;
  int _scrollBack = 0;
  double _pinchBaseCount = 60;

  int get _maxScroll {
    final total = widget.candles.length;
    final count = _visibleCount.clamp(_minVisible, total);
    return math.max(0, total - count);
  }

  List<Map<String, dynamic>> get _visibleCandles {
    if (widget.candles.isEmpty) return widget.candles;
    final total = widget.candles.length;
    final count = _visibleCount.clamp(_minVisible, total);
    final back = _scrollBack.clamp(0, _maxScroll);
    final end = total - back;
    return widget.candles.sublist(end - count, end);
  }

  double? get _currentPrice {
    if (widget.candles.isEmpty) return null;
    final v = widget.candles.last['close'];
    return v is num ? v.toDouble() : double.tryParse('$v');
  }

  void _zoomIn() => setState(() {
        _visibleCount = (_visibleCount * 0.72).round().clamp(_minVisible, widget.candles.length);
        _scrollBack = _scrollBack.clamp(0, _maxScroll);
      });

  void _zoomOut() => setState(() {
        _visibleCount = (_visibleCount * 1.35).round().clamp(_minVisible, widget.candles.length);
        _scrollBack = _scrollBack.clamp(0, _maxScroll);
      });

  void _panOlder() => setState(() => _scrollBack = (_scrollBack + 8).clamp(0, _maxScroll));

  void _panNewer() => setState(() => _scrollBack = (_scrollBack - 8).clamp(0, _maxScroll));

  void _resetView() => setState(() {
        _visibleCount = 60.clamp(_minVisible, widget.candles.length);
        _scrollBack = 0;
      });

  void _onScaleStart(ScaleStartDetails _) => _pinchBaseCount = _visibleCount.toDouble();

  void _onScaleUpdate(ScaleUpdateDetails d) {
    setState(() {
      if ((d.scale - 1).abs() > 0.02) {
        final next = (_pinchBaseCount / d.scale).round();
        _visibleCount = next.clamp(_minVisible, widget.candles.length);
      }
      if (d.focalPointDelta.dx.abs() > 0.5) {
        final step = (d.focalPointDelta.dx / 6).round();
        if (step != 0) _scrollBack = (_scrollBack - step).clamp(0, _maxScroll);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    if (widget.loading) {
      return const SizedBox(
        height: _chartHeight,
        child: Center(child: CircularProgressIndicator(color: AppColors.accent)),
      );
    }
    if (widget.candles.length < 3) {
      return const SizedBox(
        height: _chartHeight,
        child: Center(child: Text('No chart data', style: TextStyle(color: AppColors.textMuted))),
      );
    }

    final visible = _visibleCandles;
    final current = _currentPrice;
    final zoomPct = ((widget.candles.length / _visibleCount.clamp(1, widget.candles.length)) * 100).round();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 6),
          child: Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              Text('Chart · ${widget.interval}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.accent)),
              if (current != null)
                Text('Last ${_fmt(current)}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.gold)),
              if (widget.support != null) const _LegendDot(color: AppColors.profit, label: 'Support'),
              if (widget.resistance != null) const _LegendDot(color: AppColors.loss, label: 'Resistance'),
              if (widget.entry != null) const _LegendDot(color: AppColors.accent, label: 'Entry'),
            ],
          ),
        ),
        SizedBox(
          height: _chartHeight,
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              GestureDetector(
                behavior: HitTestBehavior.opaque,
                onScaleStart: _onScaleStart,
                onScaleUpdate: _onScaleUpdate,
                child: CustomPaint(
                  size: const Size(double.infinity, _chartHeight),
                  painter: _CandlePainter(
                    candles: visible,
                    priceAxisWidth: _priceAxisWidth,
                    currentPrice: current,
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
                ),
              ),
              Positioned(
                left: 6,
                bottom: 6,
                child: _ChartControls(
                  zoomPct: zoomPct,
                  canPanOlder: _scrollBack < _maxScroll,
                  canPanNewer: _scrollBack > 0,
                  onZoomIn: _zoomIn,
                  onZoomOut: _zoomOut,
                  onPanOlder: _panOlder,
                  onPanNewer: _panNewer,
                  onReset: _resetView,
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 6, left: 4, right: 4),
          child: Text(
            'Pinch to zoom · drag left/right · use ◀ ▶ buttons',
            style: TextStyle(fontSize: 10, color: AppColors.textMuted.withValues(alpha: 0.85)),
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }

  String _fmt(double price) => price >= 1000 ? price.toStringAsFixed(2) : price.toStringAsFixed(4);
}

class _ChartControls extends StatelessWidget {
  final int zoomPct;
  final bool canPanOlder;
  final bool canPanNewer;
  final VoidCallback onZoomIn;
  final VoidCallback onZoomOut;
  final VoidCallback onPanOlder;
  final VoidCallback onPanNewer;
  final VoidCallback onReset;

  const _ChartControls({
    required this.zoomPct,
    required this.canPanOlder,
    required this.canPanNewer,
    required this.onZoomIn,
    required this.onZoomOut,
    required this.onPanOlder,
    required this.onPanNewer,
    required this.onReset,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.bg.withValues(alpha: 0.92),
      elevation: 4,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.border),
        ),
        padding: const EdgeInsets.all(4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _CtrlBtn(icon: Icons.add, onTap: onZoomIn, tooltip: 'Zoom in'),
                const SizedBox(width: 4),
                _CtrlBtn(icon: Icons.remove, onTap: onZoomOut, tooltip: 'Zoom out'),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _CtrlBtn(icon: Icons.chevron_left, onTap: canPanOlder ? onPanOlder : null, tooltip: 'Older candles'),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: Text('$zoomPct%', style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.accent)),
                ),
                _CtrlBtn(icon: Icons.chevron_right, onTap: canPanNewer ? onPanNewer : null, tooltip: 'Newer candles'),
              ],
            ),
            const SizedBox(height: 4),
            _CtrlBtn(icon: Icons.center_focus_strong, onTap: onReset, tooltip: 'Reset to live', small: true),
          ],
        ),
      ),
    );
  }
}

class _CtrlBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  final String tooltip;
  final bool small;

  const _CtrlBtn({required this.icon, required this.onTap, required this.tooltip, this.small = false});

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(6),
        child: Container(
          width: small ? 72 : 34,
          height: small ? 28 : 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: enabled ? AppColors.bgElevated : AppColors.bgElevated.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: AppColors.border),
          ),
          child: Icon(icon, size: small ? 16 : 18, color: enabled ? AppColors.accent : AppColors.textMuted),
        ),
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
  final double priceAxisWidth;
  final double? currentPrice;
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
    required this.priceAxisWidth,
    this.currentPrice,
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
    final chartW = size.width - priceAxisWidth;
    if (chartW <= 0 || candles.isEmpty) return;

    final lows = candles.map((c) => (c['low'] as num).toDouble()).toList();
    final highs = candles.map((c) => (c['high'] as num).toDouble()).toList();
    var minY = lows.reduce(math.min);
    var maxY = highs.reduce(math.max);
    for (final p in [entry, stopLoss, target, support, resistance, strategyLine, expectedMoveLow, expectedMoveHigh, currentPrice]) {
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
    double priceOf(double y) => maxY - (y / size.height) * range;

    _drawPriceAxis(canvas, size, chartW, minY, maxY, range, yOf, priceOf);

    if (expectedMoveLow != null && expectedMoveHigh != null && expectedMoveLow! > 0 && expectedMoveHigh! > 0) {
      final top = yOf(math.max(expectedMoveLow!, expectedMoveHigh!));
      final bottom = yOf(math.min(expectedMoveLow!, expectedMoveHigh!));
      final zoneColor = prediction == 'bearish'
          ? AppColors.loss.withValues(alpha: 0.12)
          : AppColors.profit.withValues(alpha: 0.12);
      canvas.drawRect(Rect.fromLTRB(0, top, chartW, bottom), Paint()..color = zoneColor);
    }

    final gridPaint = Paint()..color = AppColors.border.withValues(alpha: 0.35);
    for (var i = 1; i < 4; i++) {
      final y = size.height * i / 4;
      canvas.drawLine(Offset(0, y), Offset(chartW, y), gridPaint);
    }

    final candleW = chartW / candles.length;
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

    if (currentPrice != null && currentPrice! > 0) {
      final y = yOf(currentPrice!);
      final dash = Paint()
        ..color = AppColors.gold.withValues(alpha: 0.85)
        ..strokeWidth = 1.2;
      var x = 0.0;
      while (x < chartW) {
        canvas.drawLine(Offset(x, y), Offset(math.min(x + 5, chartW), y), dash);
        x += 10;
      }
      _drawAxisPriceTag(canvas, chartW, size.width, size.height, y, 'NOW ${_fmt(currentPrice!)}', AppColors.gold, bold: true);
    }

    final levels = <_ChartLevel>[];
    void addLevel(double? price, Color color, String label, {bool dashed = true}) {
      if (price == null || price <= 0) return;
      levels.add(_ChartLevel(price: price, color: color, label: label, dashed: dashed));
    }

    addLevel(support, AppColors.profit, 'Sup', dashed: false);
    addLevel(resistance, AppColors.loss, 'Res', dashed: false);
    addLevel(strategyLine, AppColors.accentBlue, 'Strat');
    addLevel(entry, AppColors.accent, 'Entry');
    addLevel(stopLoss, AppColors.loss, 'SL');
    addLevel(target, AppColors.profit, 'T1');

    final merged = _mergeCloseLevels(levels, range * 0.0015);
    merged.sort((a, b) => yOf(b.price).compareTo(yOf(a.price)));

    const minGap = 14.0;
    const labelH = 12.0;
    final placedYs = <double>[];

    for (final lv in merged) {
      final lineY = yOf(lv.price);
      var labelY = lineY - labelH / 2;
      labelY = labelY.clamp(2.0, size.height - labelH - 2);
      for (final py in placedYs) {
        if ((labelY - py).abs() < minGap) labelY = py + minGap;
      }
      labelY = labelY.clamp(2.0, size.height - labelH - 2);
      placedYs.add(labelY);

      final paint = Paint()..color = lv.color..strokeWidth = lv.dashed ? 1.2 : 1.6;
      if (lv.dashed) {
        var x = 0.0;
        while (x < chartW) {
          canvas.drawLine(Offset(x, lineY), Offset(math.min(x + 6, chartW), lineY), paint);
          x += 12;
        }
      } else {
        canvas.drawLine(Offset(0, lineY), Offset(chartW, lineY), paint);
      }

      final tp = TextPainter(
        text: TextSpan(text: '${lv.label} ${_fmt(lv.price)}', style: TextStyle(color: lv.color, fontSize: 9, fontWeight: FontWeight.w700)),
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: chartW * 0.45);
      final lx = 4.0;
      final bg = RRect.fromRectAndRadius(Rect.fromLTWH(lx - 2, labelY - 1, tp.width + 4, tp.height + 2), const Radius.circular(3));
      canvas.drawRRect(bg, Paint()..color = AppColors.bg.withValues(alpha: 0.88));
      tp.paint(canvas, Offset(lx, labelY));
    }

    if (prediction != null && prediction!.isNotEmpty) {
      final arrow = prediction == 'bullish' ? '↑ BULL' : (prediction == 'bearish' ? '↓ BEAR' : '↔');
      final tp = TextPainter(
        text: TextSpan(text: arrow, style: const TextStyle(color: AppColors.gold, fontSize: 11, fontWeight: FontWeight.w800)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(6, 6));
    }
  }

  void _drawPriceAxis(Canvas canvas, Size size, double chartW, double minY, double maxY, double range, double Function(double) yOf, double Function(double) priceOf) {
    final axisX = chartW;
    canvas.drawLine(Offset(axisX, 0), Offset(axisX, size.height), Paint()..color = AppColors.border..strokeWidth = 1);

    for (var i = 0; i <= 5; i++) {
      final frac = i / 5;
      final y = size.height * frac;
      final price = priceOf(y);
      canvas.drawLine(Offset(chartW - 4, y), Offset(size.width, y), Paint()..color = AppColors.border.withValues(alpha: 0.5)..strokeWidth = 0.5);
      _drawAxisPriceTag(canvas, chartW, size.width, size.height, y, _fmt(price), AppColors.textMuted);
    }
  }

  void _drawAxisPriceTag(Canvas canvas, double chartW, double totalW, double chartH, double y, String text, Color color, {bool bold = false}) {
    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(color: color, fontSize: bold ? 10 : 9, fontWeight: bold ? FontWeight.w800 : FontWeight.w600),
      ),
      textDirection: TextDirection.ltr,
    )..layout(maxWidth: priceAxisWidth - 4);
    var ty = y - tp.height / 2;
    ty = ty.clamp(2.0, chartH - tp.height - 2);
    final tx = chartW + 3;
    final bg = RRect.fromRectAndRadius(
      Rect.fromLTWH(tx - 1, ty - 1, math.min(tp.width + 2, totalW - tx - 1), tp.height + 2),
      const Radius.circular(2),
    );
    canvas.drawRRect(bg, Paint()..color = AppColors.bg.withValues(alpha: bold ? 0.95 : 0.75));
    tp.paint(canvas, Offset(tx, ty));
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
      old.currentPrice != currentPrice ||
      old.entry != entry ||
      old.stopLoss != stopLoss ||
      old.target != target;
}

class _ChartLevel {
  final double price;
  final Color color;
  final String label;
  final bool dashed;

  const _ChartLevel({required this.price, required this.color, required this.label, this.dashed = true});
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
