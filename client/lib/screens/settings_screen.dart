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
  String _experience = 'Scalp Futures';
  bool _togglingTrading = false;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    final p = await UserProfileStore.load();
    _nameController.text = p.name;
    _emailController.text = p.email;
    _experience = p.experience;
    if (mounted) setState(() {});
  }

  Future<void> _saveProfile() async {
    await UserProfileStore.save(UserProfile(
      name: _nameController.text.trim().isEmpty ? 'Trader' : _nameController.text.trim(),
      email: _emailController.text.trim(),
      experience: _experience,
      goal: 'Signals only',
    ));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Profile saved'), backgroundColor: AppColors.profit),
      );
    }
  }

  Future<void> _setTrading(bool start) async {
    setState(() => _togglingTrading = true);
    try {
      final api = ref.read(apiServiceProvider);
      if (start) {
        await api.startTrading();
      } else {
        await api.stopTrading();
      }
      ref.invalidate(tradingSettingsProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(start ? 'Signal engine started' : 'Signal engine paused'),
            backgroundColor: start ? AppColors.profit : AppColors.warn,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e'), backgroundColor: AppColors.loss),
        );
      }
    } finally {
      if (mounted) setState(() => _togglingTrading = false);
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
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
                  Text('ScalpTrack · Signals only', style: TextStyle(fontSize: 12, color: AppColors.accent)),
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
                key: ValueKey(_experience),
                initialValue: _experience,
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
          data: (cfg) {
            final paused = cfg['trading_paused'] == true;
            return Column(
              children: [
                PremiumCard(
                  highlight: !paused,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            paused ? Icons.pause_circle_filled : Icons.play_circle_filled,
                            color: paused ? AppColors.warn : AppColors.profit,
                            size: 28,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  cfg['status_label'] ?? (paused ? 'PAUSED' : 'RUNNING'),
                                  style: TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w800,
                                    color: paused ? AppColors.warn : AppColors.profit,
                                  ),
                                ),
                                Text(
                                  paused
                                      ? 'No new signals until you tap Start'
                                      : 'Delta × Binance Alpha engine is scanning live',
                                  style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      SizedBox(
                        width: double.infinity,
                        height: 48,
                        child: ElevatedButton.icon(
                          onPressed: _togglingTrading ? null : () => _setTrading(paused),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: paused ? AppColors.profit : AppColors.loss,
                            foregroundColor: AppColors.bg,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                          icon: _togglingTrading
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.bg),
                                )
                              : Icon(paused ? Icons.play_arrow : Icons.stop, size: 22),
                          label: Text(
                            _togglingTrading ? 'Please wait…' : (paused ? 'START SIGNALS' : 'PAUSE SIGNALS'),
                            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                PremiumCard(
                  highlight: true,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('SIGNAL ENGINE', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1.2)),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          StatTile(label: 'MAX / DAY', value: '${cfg['max_signals_per_day'] ?? 10}'),
                          StatTile(label: 'MIN SCORE', value: '${cfg['min_confidence_pct'] ?? 70}%'),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          StatTile(
                            label: 'TODAY',
                            value: '${cfg['take_count_today'] ?? cfg['exchange_trades_today'] ?? 0}',
                            valueColor: AppColors.accentBlue,
                          ),
                          StatTile(
                            label: 'GRADE CAP',
                            value: 'A+ ${cfg['max_a_plus_per_day'] ?? 3}/day',
                            valueColor: AppColors.gold,
                          ),
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
                          cfg['why_this_trade'] ?? '70+ confluence · Delta options + Binance derivatives · news & structure',
                          style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.45),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            );
          },
          loading: () => const PremiumCard(child: Center(child: CircularProgressIndicator(color: AppColors.accent))),
          error: (_, __) => const PremiumCard(child: Text('Loading signal engine…', style: TextStyle(color: AppColors.textMuted))),
        ),
        const SizedBox(height: 20),
        PremiumCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: const [
              Text('How it works', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.text)),
              SizedBox(height: 8),
              Text(
                '• Delta × Binance Alpha: 70+ confluence · grade A+/A/B\n'
                '• Derivatives: OI, funding, L/S, taker flow, liq map\n'
                '• Delta options straddle with exact contracts when IV is cheap\n'
                '• News sentiment + market profile on every signal\n'
                '• Signals only — no auto-trade in this build\n'
                '• NO TRADE is normal — quality over quantity',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted, height: 1.55),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
