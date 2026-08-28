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

  String _rrLabel(double rr) {
    if (rr >= 1.9) return '1:2';
    if (rr >= 0.9) return '1:1';
    return '1:${rr.toStringAsFixed(1)}';
  }

  Future<void> showTakeSignal({
    required String symbol,
    required String direction,
    required String setup,
    required int confidence,
    required double entry,
    required double sl,
    required double target,
    double riskReward = 2.0,
    double riskInr = 100,
    double targetInr = 200,
    String grade = 'A+',
  }) async {
    final key = '$symbol-$setup-${DateTime.now().toIso8601String().substring(0, 16)}';
    if (_notified.contains(key)) return;
    _notified.add(key);
    if (_notified.length > 200) _notified.clear();

    final rr = _rrLabel(riskReward);
    const android = AndroidNotificationDetails(
      'scalp_signals',
      'Best Scalp Signals',
      channelDescription: 'A+ signals with 1:2 or 1:1 R:R on top movers',
      importance: Importance.max,
      priority: Priority.high,
      styleInformation: BigTextStyleInformation(''),
    );

    await _plugin.show(
      symbol.hashCode,
      '🎯 $grade $direction $symbol · $rr R:R ($confidence%)',
      '$setup · Risk ₹${riskInr.toStringAsFixed(0)} → Target ₹${targetInr.toStringAsFixed(0)} · Entry $entry · SL $sl · T1 $target',
      NotificationDetails(
        android: android.copyWith(
          styleInformation: BigTextStyleInformation(
            '$setup scalp on $symbol\n'
            'R:R $rr · Risk ₹${riskInr.toStringAsFixed(0)} → Win ₹${targetInr.toStringAsFixed(0)}\n'
            'Entry $entry · SL $sl · Target $target',
          ),
        ),
      ),
    );
  }
}

extension on AndroidNotificationDetails {
  AndroidNotificationDetails copyWith({BigTextStyleInformation? styleInformation}) {
    return AndroidNotificationDetails(
      channelId,
      channelName,
      channelDescription: channelDescription,
      importance: importance,
      priority: priority,
      styleInformation: styleInformation ?? this.styleInformation,
    );
  }
}
