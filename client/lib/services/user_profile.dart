import 'package:shared_preferences/shared_preferences.dart';

class UserProfile {
  final String name;
  final String email;
  final String experience;
  final String goal;

  const UserProfile({
    this.name = 'Trader',
    this.email = '',
    this.experience = 'Scalp Futures',
    this.goal = 'Scalp ₹200+ per win · 1:2 R:R on 24h movers',
  });

  UserProfile copyWith({String? name, String? email, String? experience, String? goal}) => UserProfile(
        name: name ?? this.name,
        email: email ?? this.email,
        experience: experience ?? this.experience,
        goal: goal ?? this.goal,
      );
}

class UserProfileStore {
  static const _kName = 'user_name';
  static const _kEmail = 'user_email';
  static const _kExp = 'user_experience';
  static const _kGoal = 'user_goal';

  static Future<UserProfile> load() async {
    final p = await SharedPreferences.getInstance();
    return UserProfile(
      name: p.getString(_kName) ?? 'Trader',
      email: p.getString(_kEmail) ?? '',
      experience: p.getString(_kExp) ?? 'Scalp Futures',
      goal: p.getString(_kGoal) ?? 'Scalp ₹200+ per win · 1:2 R:R on 24h movers',
    );
  }

  static Future<void> save(UserProfile profile) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kName, profile.name);
    await p.setString(_kEmail, profile.email);
    await p.setString(_kExp, profile.experience);
    await p.setString(_kGoal, profile.goal);
  }
}
