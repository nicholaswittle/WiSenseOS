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
  List<EngineTaskStatus> _recentTasks = const [];
  EngineTaskStatus? _focusedTask;

  bool get loading => _loading;
  bool get runningQualification => _runningQualification;
  String? get error => _error;
  EngineTelemetryReport? get telemetry => _telemetry;
  List<EngineTaskStatus> get recentTasks => _recentTasks;
  List<EngineTaskStatus> get activeTasks =>
      _recentTasks.where((task) => task.isActive).toList(growable: false);
  EngineTaskStatus? get focusedTask => _focusedTask;

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        client.getTelemetry(),
        client.listTasks(limit: 20),
      ]);
      _telemetry = results[0] as EngineTelemetryReport;
      _recentTasks = results[1] as List<EngineTaskStatus>;

      final preferredId = _focusedTask?.taskId;
      final active = activeTasks;
      EngineTaskStatus? nextFocus;
      if (preferredId != null) {
        nextFocus = _recentTasks.where((t) => t.taskId == preferredId).firstOrNull;
      }
      nextFocus ??= active.firstOrNull ?? _recentTasks.firstOrNull;
      if (nextFocus != null) {
        _focusedTask = await client.getTask(nextFocus.taskId);
      } else {
        _focusedTask = null;
      }

      _loading = false;
      notifyListeners();
    } catch (e) {
      _loading = false;
      _error = 'Failed to load command view: $e';
      notifyListeners();
    }
  }

  Future<void> focusTask(String taskId) async {
    _error = null;
    notifyListeners();
    try {
      _focusedTask = await client.getTask(taskId);
      notifyListeners();
    } catch (e) {
      _error = 'Failed to load task $taskId: $e';
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
