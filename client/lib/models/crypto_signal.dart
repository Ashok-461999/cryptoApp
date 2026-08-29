import 'package:intl/intl.dart';

import '../utils/leveraged_pnl.dart' as lev;

class CryptoSignal {
  final String symbol;
  final String direction;
  final String setup;
  final String tradeDecision;
  final int confidence;
  final double entryPrice;
  final double stopLossPrice;
  final double target1Price;
  final double target2Price;
  final double stopLossPct;
  final double target1Pct;
  final double riskReward;
  final String strictSlRule;
  final String slType;
  final int leverage;
  final int maxLeverageAllowed;
  final double liquidationPrice;
  final double liquidationBufferPct;
  final double quantity;
  final double marginUsdt;
  final double maxLossUsdt;
  final double targetProfitUsdt;
  final double riskPercent;
  final bool canAfford;
  final String tradePlan;
  final String tier;
  final String category;
  final double targetPnlInr;
  final double maxLossInr;
  final bool spreadWarning;
  final String timestamp;
  final int? tradeId;
  final String status;
  final String decisionReason;
  final String regime;
  final String regimeSummary;
  final String slBasis;
  final List<String> validityPoints;
  final double? exitPrice;
  final double marginInr;
  final double positionInr;
  final double capitalInr;
  final double riskPerTradeInr;
  final bool notify;
  final String signalGrade;
  final String priorityTier;
  final String priorityLabel;
  final String rrLabel;
  final String chartTimeframe;
  final String entryTimeframe;
  final bool userTaken;
  final bool executedOnExchange;
  final String refStatus;
  final double refPnlInr;
  final double livePnlInr;
  final String targetProfitNote;

  CryptoSignal({
    required this.symbol,
    required this.direction,
    required this.setup,
    required this.tradeDecision,
    required this.confidence,
    required this.entryPrice,
    required this.stopLossPrice,
    required this.target1Price,
    required this.target2Price,
    required this.stopLossPct,
    required this.target1Pct,
    required this.riskReward,
    required this.strictSlRule,
    required this.slType,
    required this.leverage,
    required this.maxLeverageAllowed,
    required this.liquidationPrice,
    required this.liquidationBufferPct,
    required this.quantity,
    required this.marginUsdt,
    required this.maxLossUsdt,
    required this.targetProfitUsdt,
    required this.riskPercent,
    required this.canAfford,
    required this.tradePlan,
    required this.tier,
    required this.category,
    required this.targetPnlInr,
    required this.maxLossInr,
    required this.spreadWarning,
    required this.timestamp,
    this.tradeId,
    this.status = 'OPEN',
    this.decisionReason = '',
    this.regime = '',
    this.regimeSummary = '',
    this.slBasis = '',
    this.validityPoints = const [],
    this.exitPrice,
    this.marginInr = 0,
    this.positionInr = 0,
    this.capitalInr = 20000,
    this.riskPerTradeInr = 100,
    this.notify = false,
    this.signalGrade = 'B',
    this.priorityTier = 'NORMAL',
    this.priorityLabel = '',
    this.rrLabel = '',
    this.chartTimeframe = '5m',
    this.entryTimeframe = '1m',
    this.userTaken = false,
    this.executedOnExchange = false,
    this.refStatus = 'LIVE',
    this.refPnlInr = 0,
    this.livePnlInr = 0,
    this.targetProfitNote = '',
  });

  factory CryptoSignal.fromJson(Map<String, dynamic> j) {
    double d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v') ?? 0;
    int i(dynamic v) => (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
    return CryptoSignal(
      symbol: j['symbol'] ?? '',
      direction: j['direction'] ?? '',
      setup: j['setup'] ?? '',
      tradeDecision: j['trade_decision'] ?? '',
      confidence: i(j['confidence']),
      entryPrice: d(j['entry_price']),
      stopLossPrice: d(j['stop_loss_price']),
      target1Price: d(j['target_1_price']),
      target2Price: d(j['target_2_price']),
      stopLossPct: d(j['stop_loss_pct']),
      target1Pct: d(j['target_1_pct']),
      riskReward: d(j['risk_reward']),
      strictSlRule: j['strict_sl_rule'] ?? '',
      slType: j['sl_type'] ?? 'HARD',
      leverage: i(j['leverage']),
      maxLeverageAllowed: i(j['max_leverage_allowed']),
      liquidationPrice: d(j['liquidation_price']),
      liquidationBufferPct: d(j['liquidation_buffer_pct']),
      quantity: d(j['quantity']),
      marginUsdt: d(j['margin_usdt']),
      maxLossUsdt: d(j['max_loss_usdt']),
      targetProfitUsdt: d(j['target_profit_usdt']),
      riskPercent: d(j['risk_percent']),
      canAfford: j['can_afford'] == true,
      tradePlan: j['trade_plan'] ?? '',
      tier: j['tier'] ?? 'C',
      category: j['category'] ?? 'alt',
      targetPnlInr: d(j['target_pnl_inr']),
      maxLossInr: d(j['max_loss_inr']),
      spreadWarning: j['spread_warning'] == true,
      timestamp: j['timestamp'] ?? '',
      tradeId: j['trade_id'] != null ? i(j['trade_id']) : null,
      status: j['status'] ?? 'OPEN',
      decisionReason: j['decision_reason'] ?? '',
      regime: j['regime'] ?? '',
      regimeSummary: j['regime_summary'] ?? '',
      slBasis: j['sl_basis'] ?? '',
      validityPoints: (j['validity_points'] as List? ?? []).map((e) => '$e').toList(),
      exitPrice: j['exit_price'] != null ? d(j['exit_price']) : null,
      marginInr: d(j['margin_inr']),
      positionInr: d(j['position_inr'] ?? (d(j['margin_inr']) * i(j['leverage']))),
      capitalInr: d(j['capital_inr'] ?? 20000),
      riskPerTradeInr: d(j['risk_per_trade_inr'] ?? 100),
      notify: j['notify'] == true,
      signalGrade: j['signal_grade'] ?? 'B',
      priorityTier: j['priority_tier'] ?? 'NORMAL',
      priorityLabel: j['priority_label'] ?? '',
      rrLabel: j['rr_label'] ?? '',
      chartTimeframe: j['chart_timeframe'] ?? '5m',
      entryTimeframe: j['entry_timeframe'] ?? '1m',
      userTaken: j['user_taken'] == true,
      executedOnExchange: j['executed_on_exchange'] == true,
      refStatus: j['ref_status'] ?? j['ref_outcome'] ?? 'LIVE',
      refPnlInr: d(j['ref_pnl_inr']),
      livePnlInr: d(j['live_pnl_inr']),
      targetProfitNote: j['target_profit_note'] ?? '',
    );
  }

  bool get isTaken => userTaken;

  bool get isHighPriority => priorityTier == 'HIGH';

  String get displayPriorityLabel {
    if (priorityLabel.isNotEmpty) return priorityLabel;
    if (riskReward >= 0.95) return 'A+ 1:1';
    if (notify || confidence >= 82) return 'SCALP';
    return '';
  }

  double get effectivePositionInr =>
      positionInr > 0 ? positionInr : lev.positionInr(marginInr: marginInr, leverage: leverage);

  double get effectiveMaxLossInr => lev.leveragedPnlInr(
        marginInr: marginInr,
        leverage: leverage,
        entry: entryPrice,
        levelPrice: stopLossPrice,
      );

  double get effectiveTargetProfitInr => lev.leveragedPnlInr(
        marginInr: marginInr,
        leverage: leverage,
        entry: entryPrice,
        levelPrice: target1Price,
      );

  CryptoSignal copyWith({
    int? tradeId,
    String? status,
    bool? userTaken,
    String? refStatus,
    double? refPnlInr,
    double? livePnlInr,
  }) {
    return CryptoSignal(
      symbol: symbol,
      direction: direction,
      setup: setup,
      tradeDecision: tradeDecision,
      confidence: confidence,
      entryPrice: entryPrice,
      stopLossPrice: stopLossPrice,
      target1Price: target1Price,
      target2Price: target2Price,
      stopLossPct: stopLossPct,
      target1Pct: target1Pct,
      riskReward: riskReward,
      strictSlRule: strictSlRule,
      slType: slType,
      leverage: leverage,
      maxLeverageAllowed: maxLeverageAllowed,
      liquidationPrice: liquidationPrice,
      liquidationBufferPct: liquidationBufferPct,
      quantity: quantity,
      marginUsdt: marginUsdt,
      maxLossUsdt: maxLossUsdt,
      targetProfitUsdt: targetProfitUsdt,
      riskPercent: riskPercent,
      canAfford: canAfford,
      tradePlan: tradePlan,
      tier: tier,
      category: category,
      targetPnlInr: targetPnlInr,
      maxLossInr: maxLossInr,
      spreadWarning: spreadWarning,
      timestamp: timestamp,
      tradeId: tradeId ?? this.tradeId,
      status: status ?? this.status,
      decisionReason: decisionReason,
      regime: regime,
      regimeSummary: regimeSummary,
      slBasis: slBasis,
      validityPoints: validityPoints,
      exitPrice: exitPrice,
      marginInr: marginInr,
      positionInr: positionInr,
      capitalInr: capitalInr,
      riskPerTradeInr: riskPerTradeInr,
      notify: notify,
      signalGrade: signalGrade,
      chartTimeframe: chartTimeframe,
      entryTimeframe: entryTimeframe,
      userTaken: userTaken ?? this.userTaken,
      executedOnExchange: executedOnExchange,
      refStatus: refStatus ?? this.refStatus,
      refPnlInr: refPnlInr ?? this.refPnlInr,
      livePnlInr: livePnlInr ?? this.livePnlInr,
    );
  }

  Map<String, dynamic> toTakePayload() {
    return {
      'symbol': symbol,
      'setup': setup,
      'direction': direction,
      'entry_price': entryPrice,
      'stop_loss_price': stopLossPrice,
      'target_1_price': target1Price,
      'target_2_price': target2Price,
      'leverage': leverage,
      'quantity': quantity,
      'margin_usdt': marginUsdt,
      'max_loss_usdt': maxLossUsdt,
      'target_profit_usdt': targetProfitUsdt,
      'confidence': confidence,
      'category': category,
      'timestamp': timestamp,
    };
  }

  bool get isTopStrategy => const {
        'structure_fib_sweep',
        'liquidity_sweep',
        'amd_model',
        'ifvg_reversal',
        'order_flow',
        'anchored_vwap',
        'volume_profile',
      }.contains(setup);

  String get topStrategyBadge => switch (setup) {
        'structure_fib_sweep' => 'S+F+L ★',
        'liquidity_sweep' => 'LIQ ★',
        'amd_model' => 'AMD ★',
        'ifvg_reversal' => 'IFVG ★',
        'order_flow' => 'FLOW ★',
        'anchored_vwap' => 'AVWAP ★',
        'volume_profile' => 'VP ★',
        _ => '★',
      };

  String get setupLabel => switch (setup) {
        'structure_fib_sweep' => 'Structure+Fib+Sweep',
        'amd_model' => 'AMD Model',
        'liquidity_sweep' => 'Liquidity Sweep',
        'ifvg_reversal' => 'IFVG',
        'order_flow' => 'Order Flow',
        'anchored_vwap' => 'Anchored VWAP',
        'volume_profile' => 'Volume Profile',
        'supply_demand' => 'Supply & Demand',
        'fibonacci_retrace' => 'Fibonacci',
        'structure_reversal' => 'Structure Reversal',
        'fvg_retest' => 'FVG Retest',
        'orb_breakout' => 'ORB Breakout',
        _ => setup.replaceAll('_', ' '),
      };

  /// When this signal was generated (local time + how long ago).
  String get signalTimeLabel {
    if (timestamp.isEmpty) return 'Time unknown';
    try {
      final dt = DateTime.parse(timestamp).toLocal();
      final diff = DateTime.now().difference(dt);
      final ago = diff.inMinutes < 1
          ? 'just now'
          : diff.inMinutes < 60
              ? '${diff.inMinutes} min ago'
              : diff.inHours < 24
                  ? '${diff.inHours} hr ago'
                  : '${diff.inDays} day ago';
      final clock = DateFormat('HH:mm:ss').format(dt);
      final date = DateFormat('dd MMM yyyy').format(dt);
      return '$date · $clock · $ago';
    } catch (_) {
      return timestamp;
    }
  }

  String get signalTimeShort {
    if (timestamp.isEmpty) return '';
    try {
      final dt = DateTime.parse(timestamp).toLocal();
      return DateFormat('HH:mm').format(dt);
    } catch (_) {
      return '';
    }
  }
}

class ActiveSignalsResponse {
  final List<CryptoSignal> signals;
  final int totalScanned;
  final int takeCountToday;
  final int takeCapToday;
  final String utcDate;

  ActiveSignalsResponse({
    required this.signals,
    required this.totalScanned,
    required this.takeCountToday,
    required this.takeCapToday,
    required this.utcDate,
  });

  factory ActiveSignalsResponse.fromJson(Map<String, dynamic> j) {
    final list = (j['signals'] as List? ?? [])
        .map((e) => CryptoSignal.fromJson(e as Map<String, dynamic>))
        .toList();
    return ActiveSignalsResponse(
      signals: list,
      totalScanned: j['total_scanned'] ?? 0,
      takeCountToday: j['take_count_today'] ?? 0,
      takeCapToday: j['take_cap_today'] ?? 15,
      utcDate: j['utc_date'] ?? '',
    );
  }
}
