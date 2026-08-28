import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../theme/app_theme.dart';

/// TradingView Lightweight Charts — pinch/pan, crosshair, right price scale.
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
  static const _chartHeight = 380.0;

  late final WebViewController _controller;
  bool _chartReady = false;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(AppColors.bg)
      ..addJavaScriptChannel(
        'ChartReady',
        onMessageReceived: (_) {
          _chartReady = true;
          _pushChartData();
        },
      )
      ..loadFlutterAsset('assets/chart/tv_chart.html');
  }

  @override
  void didUpdateWidget(covariant TradingChart oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_chartReady && !widget.loading) _pushChartData();
  }

  double? get _lastPrice {
    if (widget.candles.isEmpty) return null;
    final v = widget.candles.last['close'];
    return v is num ? v.toDouble() : double.tryParse('$v');
  }

  String _fmt(double price) => price >= 1000 ? price.toStringAsFixed(2) : price.toStringAsFixed(4);

  Future<void> _pushChartData() async {
    if (!_chartReady || widget.candles.length < 2) return;
    final payload = jsonEncode({
      'candles': widget.candles,
      'interval': widget.interval,
      'prediction': widget.prediction,
      'levels': {
        'entry': widget.entry,
        'stopLoss': widget.stopLoss,
        'target': widget.target,
        'support': widget.support,
        'resistance': widget.resistance,
        'strategyLine': widget.strategyLine,
      },
    });
    await _controller.runJavaScript('window.updateChart($payload);');
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

    final last = _lastPrice;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
          child: Wrap(
            spacing: 10,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text('Chart · ${widget.interval}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.accent)),
              if (last != null)
                Text('Last ${_fmt(last)}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.gold)),
              const _LegendDot(color: AppColors.profit, label: 'Support'),
              const _LegendDot(color: AppColors.loss, label: 'Resistance'),
              const _LegendDot(color: AppColors.accentBlue, label: 'Strategy'),
              const _LegendDot(color: AppColors.accent, label: 'Entry'),
            ],
          ),
        ),
        Container(
          height: _chartHeight,
          decoration: BoxDecoration(
            color: AppColors.bg,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.border),
          ),
          clipBehavior: Clip.antiAlias,
          child: WebViewWidget(
            controller: _controller,
            gestureRecognizers: {Factory<OneSequenceGestureRecognizer>(() => EagerGestureRecognizer())},
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            'TradingView chart · pinch to zoom · drag to scroll · crosshair on tap',
            style: TextStyle(fontSize: 10, color: AppColors.textMuted.withValues(alpha: 0.85)),
            textAlign: TextAlign.center,
          ),
        ),
      ],
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
