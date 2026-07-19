import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class CommandViewController extends ChangeNotifier {
  CommandViewController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  String? _error;
  EngineTelemetryReport? _telemetry;

  bool get loading => _loading;
  String? get error => _error;
  EngineTelemetryReport? get telemetry => _telemetry;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final report = await client.getTelemetry();
      _telemetry = report;
      _loading = false;
      notifyListeners();
    } catch (e) {
      _loading = false;
      _error = 'Failed to load telemetry: $e';
      notifyListeners();
    }
  }
}
