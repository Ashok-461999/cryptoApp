import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/live_signals_provider.dart';
import '../providers/providers.dart';
import '../services/server_config.dart';
import '../services/user_profile.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _controller = TextEditingController();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _goalController = TextEditingController();
  String _experience = 'Scalp Futures';
  String? _testResult;
  bool _testing = false;

  @override
  void initState() {
    super.initState();
    _loadUrl();
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

  Future<void> _loadUrl() async {
    final url = await ServerConfig.getBaseUrl();
    _controller.text = url.contains('127.0.0.1') || url.contains('localhost')
        ? suggestedPcUrl
        : url;
    setState(() {});
  }

  String? _validateUrl(String url) {
    if (url.isEmpty) return 'Enter PC URL';
    if (url.contains('127.0.0.1') || url.contains('localhost')) {
      return '127.0.0.1 is the phone itself — use your PC IP';
    }
    return null;
  }

  Future<void> _saveAndConnect() async {
    final url = _controller.text.trim();
    final err = _validateUrl(url);
    if (err != null) {
      setState(() => _testResult = err);
      return;
    }
    await ServerConfig.setBaseUrl(url);
    ref.invalidate(apiServiceProvider);
    ref.invalidate(healthProvider);
    ref.invalidate(accountStatsProvider);
    ref.invalidate(tradeHistoryProvider);
    ref.invalidate(tradingSettingsProvider);
    ref.invalidate(watchlistProvider);
    ref.read(liveSignalsProvider.notifier).connect(url);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Connected'), backgroundColor: AppColors.profit),
      );
    }
  }

  Future<void> _testConnection() async {
    final url = _controller.text.trim();
    final err = _validateUrl(url);
    if (err != null) {
      setState(() => _testResult = err);
      return;
    }
    setState(() {
      _testing = true;
      _testResult = null;
    });
    try {
      await ServerConfig.setBaseUrl(url);
      ref.invalidate(apiServiceProvider);
      final health = await ref.read(healthProvider.future);
      setState(() => _testResult = 'Connected ✓ ${health['service']}');
    } catch (e) {
      setState(() => _testResult = 'Failed — $e');
    } finally {
      setState(() => _testing = false);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
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
                  Text('ScalpTrack Pro', style: TextStyle(fontSize: 12, color: AppColors.accent)),
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
                const Text('ACTUAL TRADING SETUP', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1.2)),
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
                    StatTile(label: 'TARGET PROFIT', value: 'T1 ₹${(cfg['target_profit_inr_min'] ?? 330).toStringAsFixed(0)}+', valueColor: AppColors.profit),
                    StatTile(label: 'LEVERAGE', value: '${cfg['leverage_min'] ?? 35}–${cfg['leverage_max'] ?? 50}x'),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    StatTile(label: 'SIGNALS / DAY', value: '${cfg['signals_today'] ?? 0} / ${cfg['max_signals_per_day'] ?? 150}'),
                    StatTile(label: 'MIN CONF', value: '${cfg['min_confidence_pct'] ?? 76}%'),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    StatTile(label: 'MIN R:R', value: '${cfg['min_rr'] ?? 3.3}x'),
                    StatTile(label: 'DATABASE', value: '${cfg['database'] ?? 'sqlite'}'.toUpperCase()),
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
                    cfg['why_this_trade'] ?? '',
                    style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.45),
                  ),
                ),
              ],
            ),
          ),
          loading: () => const PremiumCard(child: Center(child: CircularProgressIndicator(color: AppColors.accent))),
          error: (_, __) => const PremiumCard(child: Text('Connect backend to see actual trading setup', style: TextStyle(color: AppColors.textMuted))),
        ),
        const SizedBox(height: 20),
        const Text('Backend Connection', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.text, fontSize: 14)),
        const SizedBox(height: 8),
        TextField(
          controller: _controller,
          style: const TextStyle(color: AppColors.text, fontSize: 14),
          decoration: const InputDecoration(hintText: 'http://192.168.0.2:8000'),
          keyboardType: TextInputType.url,
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: FilledButton(onPressed: _saveAndConnect, child: const Text('Save & Connect')),
            ),
            const SizedBox(width: 10),
            OutlinedButton(
              onPressed: _testing ? null : _testConnection,
              style: OutlinedButton.styleFrom(foregroundColor: AppColors.accent, side: const BorderSide(color: AppColors.border)),
              child: _testing
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Test'),
            ),
          ],
        ),
        if (_testResult != null) ...[
          const SizedBox(height: 10),
          Text(_testResult!, style: TextStyle(fontSize: 12, color: _testResult!.startsWith('Connected') ? AppColors.profit : AppColors.loss)),
        ],
        const SizedBox(height: 20),
        PremiumCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: const [
              Text('Neon Postgres (optional)', style: TextStyle(fontWeight: FontWeight.w700, color: AppColors.text)),
              SizedBox(height: 8),
              Text(
                '1. Create free DB at console.neon.tech\n'
                '2. Copy connection string\n'
                '3. Add to backend .env:\n'
                '   DATABASE_URL=postgresql://...\n'
                '4. Restart backend — all past trades auto-saved by date',
                style: TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.5, fontFamily: 'monospace'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
