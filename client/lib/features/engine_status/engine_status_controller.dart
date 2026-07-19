import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class EngineStatusController extends ChangeNotifier {
  EngineStatusController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  String? _error;
  EngineHealth? _health;
  List<EngineModelProfile> _models = const [];

  bool get loading => _loading;
  String? get error => _error;
  EngineHealth? get health => _health;
  List<EngineModelProfile> get models => _models;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        client.health(),
        client.listModels(),
      ]);
      _health = results[0] as EngineHealth;
      _models = results[1] as List<EngineModelProfile>;
      _loading = false;
      notifyListeners();
    } catch (e) {
      _loading = false;
      _error = 'Engine is offline or unreachable ($e)';
      _health = null;
      _models = const [];
      notifyListeners();
    }
  }
}
