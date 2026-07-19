import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class CommandViewController extends ChangeNotifier {
  CommandViewController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  bool _runningQualification = false;
  String? _error;
  EngineTelemetryReport? _telemetry;

  bool get loading => _loading;
  bool get runningQualification => _runningQualification;
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

  /// Runs the offline edit corpus for each configured model.
  /// Cloud models are recorded as not_applicable by the engine.
  Future<void> runOfflineQualification() async {
    if (_runningQualification) return;
    _runningQualification = true;
    _error = null;
    notifyListeners();
    try {
      final models = await client.listModels();
      for (final model in models) {
        await client.runQualification(model.name);
      }
      await refresh();
    } catch (e) {
      _error = 'Qualification run failed: $e';
    } finally {
      _runningQualification = false;
      notifyListeners();
    }
  }
}
