import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class TaskComposerController extends ChangeNotifier {
  TaskComposerController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  bool _submitting = false;
  bool _approving = false;
  bool _sendingProviderInput = false;
  bool _draftingPlan = false;
  bool _canceling = false;
  String? _error;
  List<EngineProject> _projects = const [];
  List<EngineModelProfile> _models = const [];

  EngineProject? _selectedProject;
  EngineModelProfile? _selectedChatModel;
  EngineModelProfile? _selectedBuilderModel;
  String _selectedMode = 'ask_before_changes';
  String _requestText = '';
  String _providerInputText = '';
  EngineTaskStatus? _lastSubmissionResult;
  EngineTaskPlan? _activePlan;

  bool get loading => _loading;
  bool get submitting => _submitting;
  bool get approving => _approving;
  bool get sendingProviderInput => _sendingProviderInput;
  bool get draftingPlan => _draftingPlan;
  bool get canceling => _canceling;
  String? get error => _error;
  List<EngineProject> get projects => _projects;
  List<EngineModelProfile> get models => _models;
  List<EngineModelProfile> get chatModels =>
      _models.where((model) => model.roles.contains('chat')).toList(growable: false);
  List<EngineModelProfile> get builderModels =>
      _models.where((model) => model.roles.contains('builder')).toList(growable: false);

  EngineProject? get selectedProject => _selectedProject;
  EngineModelProfile? get selectedChatModel => _selectedChatModel;
  EngineModelProfile? get selectedBuilderModel => _selectedBuilderModel;
  String get selectedMode => _selectedMode;
  String get requestText => _requestText;
  String get providerInputText => _providerInputText;
  EngineTaskStatus? get lastSubmissionResult => _lastSubmissionResult;
  EngineTaskStatus? get activeTaskStatus => _lastSubmissionResult;
  EngineTaskPlan? get activePlan => _activePlan ?? _lastSubmissionResult?.plan;

  bool get isCloudBuilderSelected =>
      _selectedBuilderModel?.isCloud == true ||
      _selectedBuilderModel?.supervisedTestingOnly == true;

  bool get isAutopilotBlockedByCloud =>
      _selectedMode == 'local_autopilot' && isCloudBuilderSelected;

  String? get autopilotBlockedReason => isAutopilotBlockedByCloud
      ? 'Local Autopilot is disabled when using a cloud builder model (supervised testing).'
      : null;

  bool get isWaitingForApproval =>
      _lastSubmissionResult?.status == 'waiting_for_approval';

  bool get isWaitingForProviderInput =>
      _lastSubmissionResult?.status == 'waiting_for_provider_input';

  bool get showCloudApprovalWarning =>
      isWaitingForApproval && isCloudBuilderSelected;

  bool get isValid =>
      _selectedProject != null &&
      _selectedChatModel != null &&
      _selectedBuilderModel != null &&
      _requestText.trim().isNotEmpty &&
      !isAutopilotBlockedByCloud &&
      !isWaitingForProviderInput &&
      !_submitting &&
      !_approving &&
      !_sendingProviderInput;

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
        _selectedChatModel ??= chatModels.firstOrNull ?? _models.first;
        _selectedBuilderModel ??= builderModels.firstOrNull ?? _models.first;
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

  void updateProviderInputText(String text) {
    _providerInputText = text;
    notifyListeners();
  }

  Future<EngineTaskStatus?> submitTask() async {
    if (!isValid) return null;

    _submitting = true;
    _error = null;
    _lastSubmissionResult = null;
    _activePlan = null;
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

  Future<EngineTaskStatus?> refreshTaskStatus() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty) return null;

    try {
      final updatedStatus = await client.getTask(currentId);
      _lastSubmissionResult = updatedStatus;
      _activePlan = updatedStatus.plan ?? _activePlan;
      notifyListeners();
      return updatedStatus;
    } catch (e) {
      _error = 'Failed to refresh task status: $e';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskStatus?> approveActiveTask() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty || !isWaitingForApproval) {
      return null;
    }

    _approving = true;
    _error = null;
    notifyListeners();

    try {
      final result = await client.approveTask(currentId);
      // The approval response only confirms the handoff. The durable task
      // endpoint owns the complete event timeline, so reload it immediately.
      _lastSubmissionResult = await client.getTask(result.taskId);
      _approving = false;
      notifyListeners();
      return _lastSubmissionResult;
    } catch (e) {
      _approving = false;
      _error = 'Task approval failed: $e';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskPlan?> draftActivePlan() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty || !isWaitingForApproval) return null;
    _draftingPlan = true;
    _error = null;
    notifyListeners();
    try {
      _activePlan = await client.draftTaskPlan(currentId);
      _draftingPlan = false;
      notifyListeners();
      return _activePlan;
    } catch (e) {
      _draftingPlan = false;
      _error = 'Failed to draft evidence plan: $e';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskStatus?> cancelActiveTask() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty || (!isWaitingForApproval && !isWaitingForProviderInput)) {
      return null;
    }
    _canceling = true;
    _error = null;
    notifyListeners();
    try {
      _lastSubmissionResult = await client.cancelTask(currentId);
      _activePlan = null;
      _canceling = false;
      notifyListeners();
      return _lastSubmissionResult;
    } catch (e) {
      _canceling = false;
      _error = 'Failed to cancel task: $e';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskStatus?> sendProviderInput() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty || !isWaitingForProviderInput || _providerInputText.trim().isEmpty) {
      return null;
    }
    _sendingProviderInput = true;
    _error = null;
    notifyListeners();
    try {
      final accepted = await client.submitProviderInput(currentId, _providerInputText.trim());
      _lastSubmissionResult = await client.getTask(accepted.taskId);
      _providerInputText = '';
      _sendingProviderInput = false;
      notifyListeners();
      return _lastSubmissionResult;
    } catch (e) {
      _sendingProviderInput = false;
      _error = 'Failed to send provider input: $e';
      notifyListeners();
      return null;
    }
  }
}
