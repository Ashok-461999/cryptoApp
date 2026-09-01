import 'package:flutter/material.dart';

import '../models/crypto_signal.dart';
import '../theme/app_theme.dart';

/// Single Section 10 report — same data on signal card and chart screen.
class AlphaSignalReport extends StatelessWidget {
  final Map<String, dynamic> report;
  final String Function(double) formatPrice;
  final bool compact;

  const AlphaSignalReport({
    super.key,
    required this.report,
    required this.formatPrice,
    this.compact = false,
  });

  factory AlphaSignalReport.fromSignal(
    CryptoSignal signal,
    String Function(double) formatPrice, {
    bool compact = false,
  }) {
    final r = signal.alphaReport;
    return AlphaSignalReport(
      report: r.isNotEmpty ? r : _fallbackReport(signal),
      formatPrice: formatPrice,
      compact: compact,
    );
  }

  static Map<String, dynamic> _fallbackReport(CryptoSignal s) {
    final deriv = s.derivatives;
    final liq = deriv['liquidation'] as Map<String, dynamic>? ?? {};
    final gexRoot = s.optionsGex;
    final gex = gexRoot['options'] as Map<String, dynamic>? ?? {};
    final mp = s.marketProfile;
    final isStraddle = s.direction == 'STRADDLE';
    final trade = <String, dynamic>{
      'entry': s.entryPrice,
      'stop_loss': s.stopLossPrice,
      'tp1': s.target1Price,
      'tp2': s.target2Price,
      'tp3': s.target3Price,
      'leverage': s.leverage,
      'liquidation_price': s.liquidationPrice,
      'invalidation': s.invalidation,
    };
    if (isStraddle) {
      trade['tp_up'] = s.target1Price;
      trade['tp_down'] = s.target2Price;
      trade['tp1_label'] = 'TP UP';
      trade['tp2_label'] = 'TP DOWN';
    }
    return {
      'header': s.signalHeader,
      'confluence': {
        'score': s.confluenceScore > 0 ? s.confluenceScore : s.confidence,
        'label': s.confluenceLabel.isNotEmpty ? s.confluenceLabel : '${s.confidence}/100',
        'grade': s.displayGrade,
        'confidence': s.confidence,
        'emoji': s.confluenceEmoji,
      },
      'prediction': s.prediction,
      'news': {
        'headline': s.newsHeadline,
        'source': s.newsSource,
        'impact': s.newsImpact,
        'sentiment_score': s.newsSentimentScore,
        'sentiment': s.newsSentiment,
        'effect': s.newsEffect,
      },
      'structure': {
        'htf_bias': s.htfBias,
        'summary': s.htfSummary,
        'sweep': s.structureAnalysis['sweep'],
        'sweep_level': s.structureAnalysis['sweep_level'],
        'entry_zone': s.structureAnalysis['entry_zone'],
        'invalidation': s.structureAnalysis['invalidation'] ?? s.invalidation,
      },
      'derivatives': {
        'oi_usdt': deriv['open_interest_usdt'] ?? 0,
        'oi_change_24h_pct': deriv['oi_change_24h_pct'] ?? 0,
        'funding_pct_8h': deriv['funding_pct_8h'] ?? 0,
        'funding_regime': deriv['funding_regime'] ?? 'neutral',
        'long_short_ratio': deriv['long_short_ratio'] ?? 1,
        'taker_ratio': deriv['taker_buy_sell_ratio'] ?? 1,
        'liq_above': liq['cluster_above'] ?? 0,
        'liq_below': liq['cluster_below'] ?? 0,
        'liq_density': liq['density'] ?? 'low',
        'cvd_trend': deriv['cvd_trend'] ?? 'flat',
        'cvd_confirming': deriv['cvd_confirming'],
      },
      'gex': {
        'available': gexRoot['available'] == true,
        'zero_gamma': gex['zero_gamma'],
        'net_gex_sign': gex['net_gex_sign'],
        'call_wall': gex['call_wall'],
        'put_wall': gex['put_wall'],
        'max_pain': gex['max_pain'],
        'iv_percentile': gex['iv_percentile'],
        'strategy_hint': gexRoot['strategy_hint'],
        'flow_bias': (gexRoot['options_flow'] as Map?)?['flow_bias'],
      },
      'market_profile': {
        'poc': mp['poc'] ?? 0,
        'vah': mp['vah'] ?? 0,
        'val': mp['val'] ?? 0,
        'position': mp['position'] ?? '',
      },
      'trade': trade,
      'meta': {
        'direction': s.direction,
        'instrument': s.instrumentType,
        'exchange': s.engine.isNotEmpty ? 'Delta × Binance' : 'Binance',
        'holding': s.holdingStyle,
        'risk_level': s.riskLevel,
        'setup_label': s.setupLabel,
      },
      'management': s.managementRules,
      'live_status': s.liveStatusMessage,
      'disclaimer': '',
      'straddle_setup': s.straddleSetup,
    };
  }

  double _d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v') ?? 0;

  String _signed(dynamic v) {
    final n = (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
    return n >= 0 ? '+$n' : '$n';
  }

  @override
  Widget build(BuildContext context) {
    final c = report['confluence'] as Map<String, dynamic>? ?? {};
    final n = report['news'] as Map<String, dynamic>? ?? {};
    final st = report['structure'] as Map<String, dynamic>? ?? {};
    final d = report['derivatives'] as Map<String, dynamic>? ?? {};
    final g = report['gex'] as Map<String, dynamic>? ?? {};
    final mp = report['market_profile'] as Map<String, dynamic>? ?? {};
    final t = report['trade'] as Map<String, dynamic>? ?? {};
    final m = report['meta'] as Map<String, dynamic>? ?? {};
    final direction = (m['direction'] ?? 'LONG').toString();
    final isStraddle = direction == 'STRADDLE';
    final grade = c['grade']?.toString() ?? 'B';
    final score = c['score'] ?? 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _headerRow(grade, score, m),
        if ((report['prediction'] ?? '').toString().isNotEmpty) ...[
          const SizedBox(height: 10),
          _box('PREDICTION', [(report['prediction'] ?? '').toString()], AppColors.accentBlue),
        ],
        if (isStraddle) _straddleSetupBlock(report['straddle_setup'] as Map<String, dynamic>? ?? {}),
        if ((n['headline'] ?? '').toString().isNotEmpty) ...[
          const SizedBox(height: 8),
          _box('NEWS SENTIMENT', [
            '${(n['impact'] ?? 'low').toString().toUpperCase()} · ${n['sentiment']} '
            '(${_signed(n['sentiment_score'])}) · ${n['effect']}',
            n['headline'].toString(),
          ], AppColors.warn),
        ],
        if ((report['live_status'] ?? '').toString().isNotEmpty) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.profit.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              report['live_status'].toString(),
              style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.profit),
            ),
          ),
        ],
        const SizedBox(height: 8),
        _box('STRUCTURE', [
          if (st['summary'] != null && st['summary'].toString().isNotEmpty) st['summary'].toString(),
          if (st['sweep'] != null && st['sweep'].toString().isNotEmpty) 'Sweep: ${st['sweep']}',
          if (_d(st['sweep_level']) > 0) 'Sweep level: ${formatPrice(_d(st['sweep_level']))}',
          if (st['entry_zone'] != null && st['entry_zone'].toString().isNotEmpty) 'Entry zone: ${st['entry_zone']}',
          if (st['invalidation'] != null && st['invalidation'].toString().isNotEmpty)
            'Invalidation: ${st['invalidation']}',
        ], AppColors.accentBlue),
        const SizedBox(height: 8),
        _derivGrid(d),
        if (g['available'] == true) ...[
          const SizedBox(height: 8),
          _box('GEX / OPTIONS', [
            'Zero γ ${g['zero_gamma']} · Net GEX ${g['net_gex_sign']}',
            'Call wall ${g['call_wall']} · Put wall ${g['put_wall']} · Max pain ${g['max_pain']}',
            'IV ${g['iv_percentile']}%${g['strategy_hint'] != null ? ' · ${g['strategy_hint']}' : ''}',
            if (g['flow_bias'] != null) 'Whale flow: ${g['flow_bias']}',
          ], AppColors.gold),
        ],
        const SizedBox(height: 8),
        _box('MARKET PROFILE', [
          'POC ${formatPrice(_d(mp['poc']))} · VAH ${formatPrice(_d(mp['vah']))} · VAL ${formatPrice(_d(mp['val']))}',
          'Position: ${mp['position']}',
        ], AppColors.textMuted),
        const SizedBox(height: 10),
        _tradeBlock(t, isStraddle, m),
        if (!compact) ..._managementAndDisclaimer(report),
      ],
    );
  }

  List<Widget> _managementAndDisclaimer(Map<String, dynamic> report) {
    final mgmt = (report['management'] as List?)?.map((e) => e.toString()).toList() ?? [];
    return [
      if (mgmt.isNotEmpty) ...[
        const SizedBox(height: 8),
        _box('MANAGEMENT', mgmt, AppColors.accent),
      ],
      if ((report['disclaimer'] ?? '').toString().isNotEmpty) ...[
        const SizedBox(height: 8),
        Text(
          report['disclaimer'].toString(),
          style: const TextStyle(fontSize: 9, color: AppColors.textMuted, height: 1.3),
        ),
      ],
    ];
  }

  Widget _straddleSetupBlock(Map<String, dynamic> ss) {
    final legs = (ss['legs'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    if (legs.isEmpty) return const SizedBox.shrink();
    final lines = <String>[
      'Action: BUY (not sell) — long straddle',
      ss['instruction']?.toString() ?? '',
      'Strike ${ss['strike']} · Expiry ${ss['expiry']} · Total premium ~${ss['total_premium']} USDT',
      ...legs.map((l) => '${l['side']} ${l['type']}: ${l['symbol']} · premium ${l['premium']} · qty ${l['qty'] ?? 1}'),
    ];
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: _box('STRADDLE SETUP — DELTA CONTRACTS', lines, AppColors.gold),
    );
  }

  Widget _headerRow(String grade, dynamic score, Map<String, dynamic> m) {
    Color gradeColor = AppColors.accentBlue;
    if (grade == 'A+') gradeColor = AppColors.gold;
    if (grade == 'A') gradeColor = AppColors.profit;
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(color: AppColors.accent.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(6)),
          child: Text('CONFLUENCE $score/100', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.accent)),
        ),
        const SizedBox(width: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(color: gradeColor.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(6)),
          child: Text('Grade $grade', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: gradeColor)),
        ),
        const Spacer(),
        Text(
          '${m['instrument'] ?? ''} · ${m['holding'] ?? ''}',
          style: const TextStyle(fontSize: 9, color: AppColors.textMuted),
        ),
      ],
    );
  }

  Widget _derivGrid(Map<String, dynamic> d) {
    final oi = _d(d['oi_usdt']);
    final oiM = oi >= 1e6 ? '\$${(oi / 1e6).toStringAsFixed(0)}M' : formatPrice(oi);
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: AppColors.bgElevated, borderRadius: BorderRadius.circular(8)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('DERIVATIVES MAP', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.accentBlue, letterSpacing: 0.6)),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _stat('OI', oiM)),
              Expanded(child: _stat('Fund', '${_d(d['funding_pct_8h']) >= 0 ? '+' : ''}${_d(d['funding_pct_8h']).toStringAsFixed(4)}%')),
              Expanded(child: _stat('L/S', _d(d['long_short_ratio']).toStringAsFixed(2))),
              Expanded(child: _stat('Taker', _d(d['taker_ratio']).toStringAsFixed(2))),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            'OI chg ${_d(d['oi_change_24h_pct']).toStringAsFixed(1)}% · CVD ${d['cvd_trend']} · Liq ↑ ${formatPrice(_d(d['liq_above']))} · ↓ ${formatPrice(_d(d['liq_below']))}',
            style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.35),
          ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 8, color: AppColors.textMuted)),
        Text(value, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppColors.text)),
      ],
    );
  }

  Widget _tradeBlock(Map<String, dynamic> t, bool isStraddle, Map<String, dynamic> m) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.bgElevated,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('TRADE PARAMETERS', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.gold, letterSpacing: 0.6)),
          const SizedBox(height: 8),
          if (isStraddle) ...[
            Row(
              children: [
                Expanded(child: _level('Entry', formatPrice(_d(t['entry'])), AppColors.accent)),
                Expanded(child: _level(t['tp1_label']?.toString() ?? 'TP ↑ WIN', formatPrice(_d(t['tp_up'] ?? t['tp1'])), AppColors.gold)),
                Expanded(child: _level(t['tp2_label']?.toString() ?? 'TP ↓ WIN', formatPrice(_d(t['tp_down'] ?? t['tp2'])), AppColors.gold)),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              (t['straddle_note'] ?? 'Both targets are profit zones — not long vs short bias').toString(),
              style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: AppColors.gold, height: 1.3),
            ),
          ]
          else
            Row(
              children: [
                Expanded(child: _level('Entry', formatPrice(_d(t['entry'])), AppColors.accent)),
                Expanded(child: _level('SL', formatPrice(_d(t['stop_loss'])), AppColors.loss)),
                Expanded(child: _level('TP1', formatPrice(_d(t['tp1'])), AppColors.profit)),
              ],
            ),
          if (!isStraddle && _d(t['tp2']) > 0) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(child: _level('TP2', formatPrice(_d(t['tp2'])), AppColors.profit)),
                if (_d(t['tp3']) > 0) Expanded(child: _level('TP3', formatPrice(_d(t['tp3'])), AppColors.profit)),
              ],
            ),
          ],
          if (isStraddle && _d(t['stop_loss']) > 0) ...[
            const SizedBox(height: 6),
            _level('STRICT SL', formatPrice(_d(t['stop_loss'])), AppColors.loss),
          ],
          const SizedBox(height: 6),
          Text(
            'Leverage ${t['leverage'] ?? m['direction']}x · Liq ${formatPrice(_d(t['liquidation_price']))} · ${m['risk_level'] ?? ''} risk',
            style: const TextStyle(fontSize: 9, color: AppColors.textMuted),
          ),
        ],
      ),
    );
  }

  Widget _level(String label, String value, Color color) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 9, color: AppColors.textMuted)),
        Text(value, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: color)),
      ],
    );
  }

  Widget _box(String title, List<String> lines, Color titleColor) {
    final filtered = lines.where((l) => l.trim().isNotEmpty).toList();
    if (filtered.isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: AppColors.bgElevated, borderRadius: BorderRadius.circular(8)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: titleColor, letterSpacing: 0.6)),
          const SizedBox(height: 4),
          ...filtered.map((l) => Text(l, style: const TextStyle(fontSize: 10, color: AppColors.textMuted, height: 1.35))),
        ],
      ),
    );
  }
}
