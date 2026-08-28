import 'package:intl/intl.dart';

/// Formats a crypto price for display (avoids float artifacts like 249.51999999999998).
String formatPrice(double p) {
  if (p >= 1000) return NumberFormat('#,##0.00').format(p);
  if (p >= 1) return p.toStringAsFixed(4);
  return p.toStringAsFixed(8);
}
