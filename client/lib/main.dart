import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/live_signals_provider.dart';
import '../providers/providers.dart';
import '../screens/account_screen.dart';
import '../screens/history_screen.dart';
import '../screens/news_screen.dart';
import '../screens/signals_screen.dart';
import '../screens/settings_screen.dart';
import '../screens/watchlist_screen.dart';
import '../services/notification_service.dart';
import '../services/server_config.dart';
import '../theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: CryptoSignalApp()));
  // Defer notifications so first frame paints faster
  Future.microtask(() => NotificationService().init());
}

class CryptoSignalApp extends ConsumerWidget {
  const CryptoSignalApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'ScalpTrack',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark(),
      home: const _HomeShell(),
    );
  }
}

class _HomeShell extends ConsumerStatefulWidget {
  const _HomeShell();

  @override
  ConsumerState<_HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<_HomeShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await ServerConfig.ensureConfigured();
    final url = await ServerConfig.getBaseUrl();
    ref.invalidate(serverUrlProvider);
    ref.invalidate(apiServiceProvider);
    ref.read(liveSignalsProvider.notifier).connect(url);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: _buildTab(_index),
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: AppColors.card,
        indicatorColor: AppColors.accent.withValues(alpha: 0.2),
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.track_changes), label: 'Tracker'),
          NavigationDestination(icon: Icon(Icons.history), label: 'History'),
          NavigationDestination(icon: Icon(Icons.account_balance_wallet), label: 'Account'),
          NavigationDestination(icon: Icon(Icons.currency_bitcoin), label: 'Markets'),
          NavigationDestination(icon: Icon(Icons.newspaper), label: 'News'),
          NavigationDestination(icon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }

  Widget _buildTab(int index) {
    return switch (index) {
      0 => const SignalsScreen(),
      1 => const HistoryScreen(),
      2 => const AccountScreen(),
      3 => const WatchlistScreen(),
      4 => const NewsScreen(),
      5 => const SettingsScreen(),
      _ => const SignalsScreen(),
    };
  }
}
