import 'package:flutter/material.dart';

class AppColors {
  static const bg = Color(0xFF070B12);
  static const bgElevated = Color(0xFF0D1117);
  static const card = Color(0xFF121A24);
  static const cardHighlight = Color(0xFF1A2433);
  static const border = Color(0xFF2A3544);
  static const text = Color(0xFFF0F6FC);
  static const textMuted = Color(0xFF8B9CB3);
  static const accent = Color(0xFF00D4AA);
  static const accentBlue = Color(0xFF4DA3FF);
  static const profit = Color(0xFF00E676);
  static const loss = Color(0xFFFF5252);
  static const warn = Color(0xFFFFB74D);
  static const gold = Color(0xFFFFD54F);

  static const gradientPrimary = LinearGradient(
    colors: [Color(0xFF00D4AA), Color(0xFF4DA3FF)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const gradientCard = LinearGradient(
    colors: [Color(0xFF141E2B), Color(0xFF0F1520)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

class AppTheme {
  static ThemeData dark() {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.bg,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.accent,
        secondary: AppColors.accentBlue,
        surface: AppColors.card,
        error: AppColors.loss,
      ),
      cardTheme: CardThemeData(
        color: AppColors.card,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.border, width: 0.5),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.bgElevated,
        indicatorColor: AppColors.accent.withValues(alpha: 0.15),
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.accent,
          foregroundColor: AppColors.bg,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.card,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
        ),
      ),
      fontFamily: 'Roboto',
      useMaterial3: true,
    );
  }
}

/// Premium card with subtle gradient border.
class PremiumCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final bool highlight;

  const PremiumCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.highlight = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: highlight ? AppColors.gradientCard : null,
        color: highlight ? null : AppColors.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: highlight ? AppColors.accent.withValues(alpha: 0.35) : AppColors.border,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: padding,
      child: child,
    );
  }
}

class StatTile extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;

  const StatTile({super.key, required this.label, required this.value, this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textMuted, letterSpacing: 0.5)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: valueColor ?? AppColors.text)),
        ],
      ),
    );
  }
}
