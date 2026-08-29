import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/providers.dart';
import '../services/user_profile.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _goalController = TextEditingController();
  String _experience = 'Scalp Futures';

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    final p = await UserProfileStore.load();
    _nameController.text = p.name;
    _emailController.text = p.email;
    _goalController.text = p.goal;
    _experience = p.experience;
    if (mounted) setState(() {});
  }

  Future<void> _saveProfile() async {
    await UserProfileStore.save(UserProfile(
      name: _nameController.text.trim().isEmpty ? 'Trader' : _nameController.text.trim(),
      email: _emailController.text.trim(),
      experience: _experience,
      goal: _goalController.text.trim(),
    ));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile saved'), backgroundColor: AppColors.profit),
      );
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _goalController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final trading = ref.watch(tradingSettingsProvider);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                gradient: AppColors.gradientPrimary,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.tune, color: AppColors.bg, size: 22),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Settings', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: AppColors.text)),
                  Text('ScalpTrack Pro · AWS Live', style: TextStyle(fontSize: 12, color: AppColors.accent)),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 20),
        PremiumCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('USER PROFILE', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1.2)),
              const SizedBox(height: 12),
              TextField(
                controller: _nameController,
                style: const TextStyle(color: AppColors.text),
                decoration: const InputDecoration(labelText: 'Name', hintText: 'Your name'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _emailController,
                style: const TextStyle(color: AppColors.text),
                decoration: const InputDecoration(labelText: 'Email (optional)'),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: _experience,
                dropdownColor: AppColors.card,
                style: const TextStyle(color: AppColors.text),
                decoration: const InputDecoration(labelText: 'Trading style'),
                items: const [
                  DropdownMenuItem(value: 'Scalp Futures', child: Text('Scalp Futures')),
                  DropdownMenuItem(value: 'Day Trade', child: Text('Day Trade')),
                  DropdownMenuItem(value: 'Swing', child: Text('Swing')),
                ],
                onChanged: (v) => setState(() => _experience = v ?? 'Scalp Futures'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _goalController,
                style: const TextStyle(color: AppColors.text),
                decoration: const InputDecoration(labelText: 'Profit goal per trade'),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton(
                  onPressed: _saveProfile,
                  style: OutlinedButton.styleFrom(foregroundColor: AppColors.accent, side: const BorderSide(color: AppColors.border)),
                  child: const Text('Save Profile'),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        trading.when(
          data: (cfg) => PremiumCard(
            highlight: true,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('LIVE SCALP SETUP', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1.2)),
                const SizedBox(height: 14),
                Row(
                  children: [
                    StatTile(label: 'CAPITAL', value: '₹${(cfg['capital_inr'] ?? 20000).toStringAsFixed(0)}'),
                    StatTile(label: 'RISK / TRADE', value: '₹${(cfg['risk_per_trade_inr'] ?? 100).toStringAsFixed(0)}', valueColor: AppColors.loss),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    StatTile(label: 'TARGET', value: '₹${(cfg['take_profit_inr'] ?? 200).toStringAsFixed(0)}+', valueColor: AppColors.profit),
                    StatTile(label: 'R:R', value: '1:${(cfg['min_rr'] ?? 2).toStringAsFixed(0)}'),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    StatTile(label: 'SIGNALS TODAY', value: '${cfg['signals_today'] ?? 0}'),
                    StatTile(label: 'MIN CONF', value: '${cfg['min_confidence_pct'] ?? 82}%'),
                  ],
                ),
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.bg.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    cfg['why_this_trade'] ?? 'Top 24h movers · 1:3 scalp · AWS backend live',
                    style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.45),
                  ),
                ),
              ],
            ),
          ),
          loading: () => const PremiumCard(child: Center(child: CircularProgressIndicator(color: AppColors.accent))),
          error: (_, __) => const PremiumCard(child: Text('Loading live setup from AWS…', style: TextStyle(color: AppColors.textMuted))),
        ),
        const SizedBox(height: 20),
        PremiumCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: const [
              Text('How to win', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.text)),
              SizedBox(height: 8),
              Text(
                '• Trade only A+ signals (82%+ confidence)\n'
                '• 10 min max hold — tight SL, bank ₹150+ at T1 (1:1)\n'
                '• Momentum scalp on top 24h movers only\n'
                '• Take notification alerts seriously\n'
                '• Max 3–5 trades/day — quality over quantity',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted, height: 1.55),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
