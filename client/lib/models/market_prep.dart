class MarketPrep {
  final String headline;
  final int signalsToday;
  final int signalCap;
  final Map<String, dynamic> macro;
  final List<Map<String, dynamic>> topNews;
  final List<MarketPrepPair> pairs;
  final List<Map<String, dynamic>> liquidationLandscape;
  final List<Map<String, dynamic>> watchlist;
  final String disclaimer;

  const MarketPrep({
    required this.headline,
    required this.signalsToday,
    required this.signalCap,
    required this.macro,
    required this.topNews,
    required this.pairs,
    required this.liquidationLandscape,
    required this.watchlist,
    required this.disclaimer,
  });

  factory MarketPrep.fromJson(Map<String, dynamic> j) {
    return MarketPrep(
      headline: j['headline']?.toString() ?? '',
      signalsToday: (j['signals_today'] as num?)?.toInt() ?? 0,
      signalCap: (j['signal_cap'] as num?)?.toInt() ?? 10,
      macro: Map<String, dynamic>.from(j['macro'] as Map? ?? {}),
      topNews: (j['top_news'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList(),
      pairs: (j['pairs'] as List? ?? [])
          .map((e) => MarketPrepPair.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      liquidationLandscape: (j['liquidation_landscape'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList(),
      watchlist: (j['watchlist'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)).toList(),
      disclaimer: j['disclaimer']?.toString() ?? '',
    );
  }
}

class MarketPrepPair {
  final String symbol;
  final String label;
  final double price;
  final double changePct24h;
  final String trend;
  final double fundingPct;
  final double oiUsdt;
  final double liqAbove;
  final double liqBelow;

  const MarketPrepPair({
    required this.symbol,
    required this.label,
    required this.price,
    required this.changePct24h,
    required this.trend,
    required this.fundingPct,
    required this.oiUsdt,
    required this.liqAbove,
    required this.liqBelow,
  });

  factory MarketPrepPair.fromJson(Map<String, dynamic> j) {
    double d(dynamic v) => (v is num) ? v.toDouble() : double.tryParse('$v') ?? 0;
    return MarketPrepPair(
      symbol: j['symbol']?.toString() ?? '',
      label: j['label']?.toString() ?? '',
      price: d(j['price']),
      changePct24h: d(j['change_pct_24h']),
      trend: j['trend']?.toString() ?? 'sideways',
      fundingPct: d(j['funding_pct']),
      oiUsdt: d(j['oi_usdt']),
      liqAbove: d(j['liq_above']),
      liqBelow: d(j['liq_below']),
    );
  }
}
