import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class TaskHistoryController extends ChangeNotifier {
  TaskHistoryController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  bool _draftingPlan = false;
  bool _cancelling = false;
  String? _error;
  List<EngineTaskStatus> _tasks = const [];
  EngineTaskStatus? _selectedTask;
  EngineTaskPlan? _currentPlan;

  bool get loading => _loading;
  bool get draftingPlan => _draftingPlan;
  bool get cancelling => _cancelling;
  String? get error => _error;
  List<EngineTaskStatus> get tasks => _tasks;
  EngineTaskStatus? get selectedTask => _selectedTask;
  EngineTaskPlan? get currentPlan => _currentPlan;

  Future<void> loadTasks() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final fetchedTasks = await client.listTasks(limit: 50);
      _tasks = fetchedTasks;

      if (_selectedTask != null) {
        _selectedTask = _tasks.firstWhere(
          (t) => t.taskId == _selectedTask!.taskId,
          orElse: () => _selectedTask!,
        );
        _currentPlan = _selectedTask!.plan ?? _currentPlan;
      } else if (_tasks.isNotEmpty) {
        _selectedTask = _tasks.first;
        _currentPlan = _selectedTask!.plan;
      }

      _loading = false;
      notifyListeners();
    } catch (e) {
      _loading = false;
      _error = 'Failed to load task history: $e';
      notifyListeners();
    }
  }

  void selectTask(EngineTaskStatus task) {
    _selectedTask = task;
    _currentPlan = task.plan;
    _error = null;
    notifyListeners();
  }

  Future<EngineTaskPlan?> draftPlan(String taskId) async {
    _draftingPlan = true;
    _error = null;
    notifyListeners();

    try {
      final plan = await client.draftTaskPlan(taskId);
      _currentPlan = plan;
      _draftingPlan = false;
      notifyListeners();
      return plan;
    } catch (e) {
      _draftingPlan = false;
      _error = 'Draft plan failed: $e';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskStatus?> cancelTask(String taskId) async {
    _cancelling = true;
    _error = null;
    notifyListeners();

    try {
      final cancelledStatus = await client.cancelTask(taskId);
      await loadTasks();
      _selectedTask = cancelledStatus;
      _cancelling = false;
      notifyListeners();
      return cancelledStatus;
    } catch (e) {
      _cancelling = false;
      _error = 'Cancel task failed: $e';
      notifyListeners();
      return null;
    }
  }
}
