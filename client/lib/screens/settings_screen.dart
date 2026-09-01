import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/providers.dart';
import '../services/client_credentials.dart';
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
  final _apiKeyController = TextEditingController();
  final _apiSecretController = TextEditingController();
  String _experience = 'Scalp Futures';
  bool _togglingTrading = false;
  bool _paperEnabled = true;
  bool _liveAutoTrade = false;
  bool _savingCreds = false;
  bool _obscureSecret = true;

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
    final creds = await ClientCredentialsStore.loadLocal();
    _apiKeyController.text = creds['api_key'] as String? ?? '';
    _apiSecretController.text = creds['api_secret'] as String? ?? '';
    _paperEnabled = creds['paper_enabled'] as bool? ?? true;
    _liveAutoTrade = creds['live_auto_trade'] as bool? ?? false;
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

  Future<void> _saveTradingCredentials() async {
    setState(() => _savingCreds = true);
    try {
      final clientId = await ClientCredentialsStore.getOrCreateClientId();
      final api = ref.read(apiServiceProvider);
      await api.saveClientCredentials(
        clientId: clientId,
        apiKey: _apiKeyController.text.trim(),
        apiSecret: _apiSecretController.text.trim(),
        paperEnabled: _paperEnabled,
        liveAutoTrade: _liveAutoTrade,
      );
      await ClientCredentialsStore.saveLocal(
        apiKey: _apiKeyController.text.trim(),
        apiSecret: _apiSecretController.text.trim(),
        paperEnabled: _paperEnabled,
        liveAutoTrade: _liveAutoTrade,
      );
      ref.invalidate(tradingSettingsProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Trading preferences saved'), backgroundColor: AppColors.profit),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Save failed: $e'), backgroundColor: AppColors.loss),
        );
      }
    } finally {
      if (mounted) setState(() => _savingCreds = false);
    }
  }

  Future<void> _resetPaperWallet() async {
    try {
      final clientId = await ClientCredentialsStore.getOrCreateClientId();
      await ref.read(apiServiceProvider).resetPaperWallet(clientId);
      ref.invalidate(tradingSettingsProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Paper wallet reset to \$100'), backgroundColor: AppColors.profit),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Reset failed: $e'), backgroundColor: AppColors.loss),
        );
      }
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
            content: Text(start ? 'Trading started — scanning & auto-trade on' : 'Trading stopped — no new signals or orders'),
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
    _goalController.dispose();
    _apiKeyController.dispose();
    _apiSecretController.dispose();
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
        PremiumCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('TRADING MODE', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1.2)),
              const SizedBox(height: 8),
              const Text(
                'Paper: \$100 USDT virtual wallet (compounds after each trade). Live: your Binance API keys for auto-trade.',
                style: TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.4),
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Paper wallet (\$100)', style: TextStyle(color: AppColors.text, fontSize: 14)),
                subtitle: const Text('Practice with virtual balance', style: TextStyle(fontSize: 11, color: AppColors.textMuted)),
                value: _paperEnabled,
                activeThumbColor: AppColors.profit,
                onChanged: (v) => setState(() => _paperEnabled = v),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Live auto-trade (Binance)', style: TextStyle(color: AppColors.text, fontSize: 14)),
                subtitle: const Text('Uses your API keys below — premium later', style: TextStyle(fontSize: 11, color: AppColors.textMuted)),
                value: _liveAutoTrade,
                activeThumbColor: AppColors.profit,
                onChanged: (v) => setState(() => _liveAutoTrade = v),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _apiKeyController,
                style: const TextStyle(color: AppColors.text),
                decoration: const InputDecoration(labelText: 'Binance API Key'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _apiSecretController,
                obscureText: _obscureSecret,
                style: const TextStyle(color: AppColors.text),
                decoration: InputDecoration(
                  labelText: 'Binance API Secret',
                  suffixIcon: IconButton(
                    icon: Icon(_obscureSecret ? Icons.visibility_off : Icons.visibility, color: AppColors.textMuted),
                    onPressed: () => setState(() => _obscureSecret = !_obscureSecret),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _savingCreds ? null : _resetPaperWallet,
                      child: const Text('Reset \$100'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton(
                      onPressed: _savingCreds ? null : _saveTradingCredentials,
                      style: ElevatedButton.styleFrom(backgroundColor: AppColors.accent, foregroundColor: AppColors.bg),
                      child: Text(_savingCreds ? 'Saving…' : 'Save Trading Setup'),
                    ),
                  ),
                ],
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
                                      ? 'No scans or Binance orders until you tap Start'
                                      : 'Scanning movers & auto-trading on Binance',
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
                            _togglingTrading ? 'Please wait…' : (paused ? 'START TRADING' : 'STOP TRADING'),
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
                      const Text('QUALITY SIGNAL SETUP', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: AppColors.accent, letterSpacing: 1.2)),
                const SizedBox(height: 14),
                Row(
                  children: [
                    StatTile(label: 'WALLET', value: '\$${(cfg['capital_usdt'] ?? 100).toString()}'),
                    StatTile(
                      label: 'MODE',
                      value: (cfg['pnl_mode'] ?? 'paper').toString().toUpperCase(),
                      valueColor: AppColors.accent,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    StatTile(label: 'USDT WALLET', value: '${cfg['binance_usdt_balance'] ?? 0}'),
                    StatTile(label: 'OPEN PNL', value: '₹${(cfg['binance_unrealized_pnl_inr'] ?? 0).toStringAsFixed(0)}'),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    StatTile(label: 'RISK / TRADE', value: '₹${(cfg['risk_per_trade_inr'] ?? 18).toStringAsFixed(0)}', valueColor: AppColors.loss),
                    StatTile(label: 'TARGET', value: '₹${(cfg['target_profit_inr_min'] ?? 18).toStringAsFixed(0)}–${(cfg['take_profit_inr_max'] ?? 25).toStringAsFixed(0)}', valueColor: AppColors.profit),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    StatTile(label: 'MAX / DAY', value: '${cfg['max_signals_per_day'] ?? 10}'),
                    StatTile(label: 'MIN CONF', value: '${cfg['min_confidence_pct'] ?? 78}%'),
                  ],
                ),
                const SizedBox(height: 14),
                if ((cfg['client']?['live_auto_trade'] == true) || cfg['auto_execute_trades'] == true) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.profit.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.profit.withValues(alpha: 0.4)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('AUTO-TRADE ON', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppColors.profit)),
                        const SizedBox(height: 4),
                        Text(
                          'Binance Futures · ${cfg['exchange_trades_today'] ?? 0}/${cfg['max_exchange_trades_per_day'] ?? 150} today · '
                          'USDT ${(cfg['binance_usdt_balance'] ?? 0).toString()}',
                          style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                        ),
                        Text(
                          cfg['pnl_mode_note'] ?? 'Real orders on Binance',
                          style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.4),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                ] else ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.accent.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      cfg['pnl_mode_note'] ?? 'Paper \$100 wallet — enable Live Auto-Trade with Binance keys above',
                      style: const TextStyle(fontSize: 11, color: AppColors.textMuted, height: 1.4),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.bg.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    cfg['why_this_trade'] ?? 'Quality signals · backtest required',
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
                '• Delta × Binance Alpha: 70+ confluence score · grade A+/A/B\n'
                '• Derivatives: OI, funding, L/S ratio, taker flow, liq map\n'
                '• News sentiment + market profile (POC/VAH/VAL) on every signal\n'
                '• BTC & Gold focus · max 10 signals/day · 5 min scan\n'
                '• Paper wallet \$100 — balance compounds after each trade\n'
                '• Live auto-trade: Binance API keys in Settings\n'
                '• NO TRADE is normal — quality over quantity builds trust',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted, height: 1.55),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
