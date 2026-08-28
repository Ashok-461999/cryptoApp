import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._();
  factory NotificationService() => _instance;
  NotificationService._();

  final _plugin = FlutterLocalNotificationsPlugin();
  final Set<String> _notified = {};

  Future<void> init() async {
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    await _plugin.initialize(const InitializationSettings(android: android));
    await _plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();
  }

  Future<void> showTakeSignal({
    required String symbol,
    required String direction,
    required String setup,
    required int confidence,
    required double entry,
    required double sl,
    required double target,
  }) async {
    final key = '$symbol-$setup-${DateTime.now().toIso8601String().substring(0, 16)}';
    if (_notified.contains(key)) return;
    _notified.add(key);
    if (_notified.length > 200) _notified.clear();

    const android = AndroidNotificationDetails(
      'scalp_signals',
      'High Confidence Signals',
      channelDescription: 'A+ signals with 85%+ confidence',
      importance: Importance.high,
      priority: Priority.high,
    );

    await _plugin.show(
      symbol.hashCode,
      '🚨 TAKE $direction $symbol ($confidence%)',
      '$setup · Entry $entry · SL $sl · T1 $target',
      const NotificationDetails(android: android),
    );
  }
}
