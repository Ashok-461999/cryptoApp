/// Futures PnL: position = margin × leverage; PnL = position × price move %.
double leveragedPnlInr({
  required double marginInr,
  required int leverage,
  required double entry,
  required double levelPrice,
}) {
  if (marginInr <= 0 || leverage <= 0 || entry <= 0 || levelPrice <= 0) return 0;
  final position = marginInr * leverage;
  return position * (entry - levelPrice).abs() / entry;
}

double positionInr({required double marginInr, required int leverage}) => marginInr * leverage;
