import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class TaskComposerController extends ChangeNotifier {
  TaskComposerController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  bool _submitting = false;
  String? _error;
  List<EngineProject> _projects = const [];
  List<EngineModelProfile> _models = const [];

  EngineProject? _selectedProject;
  EngineModelProfile? _selectedChatModel;
  EngineModelProfile? _selectedBuilderModel;
  String _selectedMode = 'ask_before_changes';
  String _requestText = '';
  EngineTaskStatus? _lastSubmissionResult;

  bool get loading => _loading;
  bool get submitting => _submitting;
  String? get error => _error;
  List<EngineProject> get projects => _projects;
  List<EngineModelProfile> get models => _models;

  EngineProject? get selectedProject => _selectedProject;
  EngineModelProfile? get selectedChatModel => _selectedChatModel;
  EngineModelProfile? get selectedBuilderModel => _selectedBuilderModel;
  String get selectedMode => _selectedMode;
  String get requestText => _requestText;
  EngineTaskStatus? get lastSubmissionResult => _lastSubmissionResult;

  bool get isCloudBuilderSelected =>
      _selectedBuilderModel?.supervisedTestingOnly == true;

  bool get isAutopilotBlockedByCloud =>
      _selectedMode == 'local_autopilot' && isCloudBuilderSelected;

  String? get autopilotBlockedReason => isAutopilotBlockedByCloud
      ? 'Local Autopilot is disabled when using a cloud builder model (supervised testing).'
      : null;

  bool get isValid =>
      _selectedProject != null &&
      _selectedChatModel != null &&
      _selectedBuilderModel != null &&
      _requestText.trim().isNotEmpty &&
      !isAutopilotBlockedByCloud &&
      !_submitting;

  Future<void> load() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        client.listProjects(),
        client.listModels(),
      ]);
      _projects = results[0] as List<EngineProject>;
      _models = results[1] as List<EngineModelProfile>;

      if (_projects.isNotEmpty && _selectedProject == null) {
        _selectedProject = _projects.first;
      }
      if (_models.isNotEmpty) {
        _selectedChatModel ??= _models.firstWhere(
          (m) => m.roles.contains('chat') || m.roles.contains('planner'),
          orElse: () => _models.first,
        );
        _selectedBuilderModel ??= _models.firstWhere(
          (m) => m.roles.contains('builder'),
          orElse: () => _models.first,
        );
      }

      _loading = false;
      notifyListeners();
    } catch (e) {
      _loading = false;
      _error = 'Failed to load projects or models: $e';
      notifyListeners();
    }
  }

  void selectProject(EngineProject? project) {
    _selectedProject = project;
    notifyListeners();
  }

  void selectChatModel(EngineModelProfile? model) {
    _selectedChatModel = model;
    notifyListeners();
  }

  void selectBuilderModel(EngineModelProfile? model) {
    _selectedBuilderModel = model;
    notifyListeners();
  }

  void selectMode(String mode) {
    _selectedMode = mode;
    notifyListeners();
  }

  void updateRequestText(String text) {
    _requestText = text;
    notifyListeners();
  }

  Future<EngineTaskStatus?> submitTask() async {
    if (!isValid) return null;

    _submitting = true;
    _error = null;
    _lastSubmissionResult = null;
    notifyListeners();

    try {
      final submission = EngineTaskSubmission(
        request: _requestText.trim(),
        projectRoot: _selectedProject!.root,
        mode: _selectedMode,
        chatModel: _selectedChatModel!.name,
        builderModel: _selectedBuilderModel!.name,
      );

      final result = await client.submitTask(submission);
      _lastSubmissionResult = result;
      _submitting = false;
      notifyListeners();
      return result;
    } catch (e) {
      _submitting = false;
      _error = 'Task submission failed: $e';
      notifyListeners();
      return null;
    }
  }
}
