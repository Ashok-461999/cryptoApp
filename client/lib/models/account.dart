import '../utils/leveraged_pnl.dart' as lev;

class AccountStats {
  final double startingCapitalUsdt;
  final double startingCapitalInr;
  final double equityUsdt;
  final double equityInr;
  final double realizedPnlUsdt;
  final double realizedPnlInr;
  final double peakEquityInr;
  final double drawdownPct;
  final int winCount;
  final int lossCount;
  final int openTrades;
  final double winRatePct;
  final String todayOutcomeSequence;
  final List<DailyPnlRow> dailyPnl;
  final List<SetupPerformanceRow> setupPerformance;
  final bool signalsUnlimited;

  AccountStats({
    required this.startingCapitalUsdt,
    required this.startingCapitalInr,
    required this.equityUsdt,
    required this.equityInr,
    required this.realizedPnlUsdt,
    required this.realizedPnlInr,
    required this.peakEquityInr,
    required this.drawdownPct,
    required this.winCount,
    required this.lossCount,
    required this.openTrades,
    required this.winRatePct,
    this.todayOutcomeSequence = '',
    this.dailyPnl = const [],
    this.setupPerformance = const [],
    this.signalsUnlimited = true,
  });

  factory AccountStats.fromJson(Map<String, dynamic> j) {
    double d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v') ?? 0;
    int i(dynamic v) => (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
    final daily = (j['daily_pnl'] as List? ?? [])
        .map((e) => DailyPnlRow.fromJson(e as Map<String, dynamic>))
        .toList();
    final setups = (j['setup_performance'] as List? ?? [])
        .map((e) => SetupPerformanceRow.fromJson(e as Map<String, dynamic>))
        .toList();
    return AccountStats(
      startingCapitalUsdt: d(j['starting_capital_usdt']),
      startingCapitalInr: d(j['starting_capital_inr']),
      equityUsdt: d(j['equity_usdt']),
      equityInr: d(j['equity_inr']),
      realizedPnlUsdt: d(j['realized_pnl_usdt']),
      realizedPnlInr: d(j['realized_pnl_inr']),
      peakEquityInr: d(j['peak_equity_inr']),
      drawdownPct: d(j['drawdown_pct']),
      winCount: i(j['win_count']),
      lossCount: i(j['loss_count']),
      openTrades: i(j['open_trades']),
      winRatePct: d(j['win_rate_pct']),
      todayOutcomeSequence: j['today_outcome_sequence']?.toString() ?? '',
      dailyPnl: daily,
      setupPerformance: setups,
      signalsUnlimited: j['signals_unlimited'] == true,
    );
  }
}

class DailyPnlRow {
  final String date;
  final int totalTrades;
  final int wins;
  final int losses;
  final double netPnlInr;
  final double equityEndInr;
  final String outcomeSequence;

  DailyPnlRow({
    required this.date,
    required this.totalTrades,
    required this.wins,
    required this.losses,
    required this.netPnlInr,
    required this.equityEndInr,
    required this.outcomeSequence,
  });

  factory DailyPnlRow.fromJson(Map<String, dynamic> j) {
    double d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v') ?? 0;
    int i(dynamic v) => (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
    return DailyPnlRow(
      date: j['date']?.toString() ?? '',
      totalTrades: i(j['total_trades']),
      wins: i(j['wins']),
      losses: i(j['losses']),
      netPnlInr: d(j['net_pnl_inr']),
      equityEndInr: d(j['equity_end_inr']),
      outcomeSequence: j['outcome_sequence']?.toString() ?? '',
    );
  }
}

class SetupPerformanceRow {
  final String setup;
  final String label;
  final int totalTrades;
  final int wins;
  final int losses;
  final double netPnlInr;
  final double winRatePct;
  final String tier;

  SetupPerformanceRow({
    required this.setup,
    required this.label,
    required this.totalTrades,
    required this.wins,
    required this.losses,
    required this.netPnlInr,
    required this.winRatePct,
    required this.tier,
  });

  factory SetupPerformanceRow.fromJson(Map<String, dynamic> j) {
    double d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v') ?? 0;
    int i(dynamic v) => (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
    return SetupPerformanceRow(
      setup: j['setup']?.toString() ?? '',
      label: j['label']?.toString() ?? '',
      totalTrades: i(j['total_trades']),
      wins: i(j['wins']),
      losses: i(j['losses']),
      netPnlInr: d(j['net_pnl_inr']),
      winRatePct: d(j['win_rate_pct']),
      tier: j['tier']?.toString() ?? 'mid',
    );
  }
}

class TradeRecord {
  final int id;
  final String symbol;
  final String setup;
  final String direction;
  final String status;
  final double entryPrice;
  final double? exitPrice;
  final double stopLossPrice;
  final double target1Price;
  final int leverage;
  final double marginUsdt;
  final double marginInr;
  final double positionInr;
  final double maxLossUsdt;
  final double maxLossInr;
  final double targetProfitUsdt;
  final double targetProfitInr;
  final double pnlUsdt;
  final double pnlInr;
  final double? livePrice;
  final double? unrealizedPnlInr;
  final bool atSl;
  final bool atTarget;
  final int confidence;
  final String category;
  final String? closeReason;
  final String createdAt;
  final String? closedAt;
  final String outcome;

  TradeRecord({
    required this.id,
    required this.symbol,
    required this.setup,
    required this.direction,
    required this.status,
    required this.entryPrice,
    this.exitPrice,
    required this.stopLossPrice,
    required this.target1Price,
    required this.leverage,
    required this.marginUsdt,
    required this.marginInr,
    this.positionInr = 0,
    required this.maxLossUsdt,
    required this.maxLossInr,
    required this.targetProfitUsdt,
    required this.targetProfitInr,
    required this.pnlUsdt,
    required this.pnlInr,
    this.livePrice,
    this.unrealizedPnlInr,
    this.atSl = false,
    this.atTarget = false,
    required this.confidence,
    required this.category,
    this.closeReason,
    required this.createdAt,
    this.closedAt,
    this.outcome = '',
  });

  factory TradeRecord.fromJson(Map<String, dynamic> j) {
    double d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v') ?? 0;
    int i(dynamic v) => (v is num) ? v.toInt() : int.tryParse('$v') ?? 0;
    return TradeRecord(
      id: i(j['id']),
      symbol: j['symbol'] ?? '',
      setup: j['setup'] ?? '',
      direction: j['direction'] ?? '',
      status: j['status'] ?? '',
      entryPrice: d(j['entry_price']),
      exitPrice: j['exit_price'] != null ? d(j['exit_price']) : null,
      stopLossPrice: d(j['stop_loss_price']),
      target1Price: d(j['target_1_price']),
      leverage: i(j['leverage']),
      marginUsdt: d(j['margin_usdt']),
      marginInr: d(j['margin_inr'] ?? (d(j['margin_usdt']) * 83)),
      positionInr: d(j['position_inr'] ?? (d(j['margin_inr'] ?? d(j['margin_usdt']) * 83) * i(j['leverage']))),
      maxLossUsdt: d(j['max_loss_usdt']),
      maxLossInr: d(j['max_loss_inr'] ?? (d(j['max_loss_usdt']) * 83)),
      targetProfitUsdt: d(j['target_profit_usdt']),
      targetProfitInr: d(j['target_profit_inr'] ?? (d(j['target_profit_usdt']) * 83)),
      pnlUsdt: d(j['pnl_usdt']),
      pnlInr: d(j['pnl_inr']),
      livePrice: j['live_price'] != null ? d(j['live_price']) : null,
      unrealizedPnlInr: j['unrealized_pnl_inr'] != null ? d(j['unrealized_pnl_inr']) : null,
      atSl: j['at_sl'] == true,
      atTarget: j['at_target'] == true,
      confidence: i(j['confidence']),
      category: j['category'] ?? '',
      closeReason: j['close_reason'],
      createdAt: j['created_at'] ?? '',
      closedAt: j['closed_at'],
      outcome: j['outcome'] ?? j['status'] ?? '',
    );
  }

  String get displayStatus => outcome.isNotEmpty ? outcome : status;

  double get effectivePositionInr => positionInr > 0 ? positionInr : lev.positionInr(marginInr: marginInr, leverage: leverage);

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
}
