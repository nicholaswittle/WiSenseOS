import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class TaskComposerController extends ChangeNotifier {
  TaskComposerController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  bool _submitting = false;
  bool _approving = false;
  bool _proposing = false;
  bool _sendingProviderInput = false;
  bool _draftingPlan = false;
  bool _canceling = false;
  String? _error;
  String? _planDraftHint;
  List<String> _planDraftCandidates = const [];
  String? _lastAction;
  List<EngineProject> _projects = const [];
  List<EngineModelProfile> _models = const [];

  EngineProject? _selectedProject;
  EngineModelProfile? _selectedChatModel;
  EngineModelProfile? _selectedBuilderModel;
  String _selectedMode = 'ask_before_changes';
  bool _offline = false;
  String _requestText = '';
  String _providerInputText = '';
  String _resolvePhrase = '';
  String? _resolveMessage;
  bool _resolving = false;
  bool _registering = false;
  EngineTaskStatus? _lastSubmissionResult;
  EngineTaskPlan? _activePlan;
  EngineTaskProposal? _activeProposal;
  Timer? _pollTimer;

  bool get loading => _loading;
  bool get submitting => _submitting;
  bool get approving => _approving;
  bool get proposing => _proposing;
  bool get sendingProviderInput => _sendingProviderInput;
  bool get draftingPlan => _draftingPlan;
  bool get canceling => _canceling;
  String? get error => _error;
  String? get planDraftHint => _planDraftHint;
  List<String> get planDraftCandidates => _planDraftCandidates;
  String? get lastAction => _lastAction;
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
  bool get offline => _offline;
  String get requestText => _requestText;
  String get providerInputText => _providerInputText;
  String get resolvePhrase => _resolvePhrase;
  String? get resolveMessage => _resolveMessage;
  bool get resolving => _resolving;
  bool get registering => _registering;
  EngineTaskStatus? get lastSubmissionResult => _lastSubmissionResult;
  EngineTaskStatus? get activeTaskStatus => _lastSubmissionResult;
  EngineTaskPlan? get activePlan => _activePlan ?? _lastSubmissionResult?.plan;
  EngineTaskProposal? get activeProposal =>
      _activeProposal ?? _lastSubmissionResult?.proposal;

  bool get isCloudBuilderSelected =>
      _selectedBuilderModel?.isCloud == true ||
      _selectedBuilderModel?.supervisedTestingOnly == true;

  /// True when no local builder profile is configured/available yet
  /// (expected before the hardware upgrade).
  bool get hasLocalBuilder =>
      builderModels.any((model) => !model.isCloud && model.available);

  bool get isCloudAssistedOnly => !hasLocalBuilder;

  bool get isAutopilotBlockedByCloud =>
      _selectedMode == 'local_autopilot' &&
      (isCloudBuilderSelected || isCloudAssistedOnly);

  String? get autopilotBlockedReason {
    if (!isAutopilotBlockedByCloud) return null;
    if (isCloudAssistedOnly) {
      return 'Local Autopilot needs a qualified offline builder. '
          'Until the hardware upgrade, use Ask Before Changes with a cloud builder (supervised testing).';
    }
    return 'Local Autopilot is disabled when using a cloud builder model (supervised testing).';
  }

  String? get offlineBlockedReason {
    if (!_offline || hasLocalBuilder) return null;
    return 'Offline mode hard-blocks every cloud model. With only cloud profiles '
        'configured, leave Offline off until a local builder is installed.';
  }

  bool get isAccepted => _lastSubmissionResult?.status == 'accepted';

  bool get isExploring => _lastSubmissionResult?.status == 'exploring';

  bool get isWaitingForApproval =>
      _lastSubmissionResult?.status == 'waiting_for_approval';

  /// Native PlanBoundPatchExecutor does not drive provider-input turns.
  /// Keep the getter for status display only — Companion does not solicit
  /// freeform "go ahead" replies as a write gate (digest approval does).
  bool get isWaitingForProviderInput =>
      _lastSubmissionResult?.status == 'waiting_for_provider_input';

  bool get showProviderInputPanel => false;

  bool get isRunning => _lastSubmissionResult?.status == 'running';

  bool get showCloudApprovalWarning =>
      isWaitingForApproval && isCloudBuilderSelected;

  bool get canDraftPlan =>
      (isAccepted || isExploring) &&
      _selectedMode == 'ask_before_changes' &&
      !_draftingPlan &&
      !_proposing;

  bool get canPrepareProposal =>
      isAccepted &&
      activePlan != null &&
      activeProposal == null &&
      !_proposing;

  bool get canCancelActiveTask =>
      isAccepted ||
      isExploring ||
      isWaitingForApproval ||
      isWaitingForProviderInput ||
      isRunning;

  bool get isValid =>
      _selectedProject != null &&
      _selectedChatModel != null &&
      _selectedBuilderModel != null &&
      _requestText.trim().isNotEmpty &&
      !isAutopilotBlockedByCloud &&
      !(_offline && isCloudAssistedOnly) &&
      !isWaitingForProviderInput &&
      !_submitting &&
      !_approving &&
      !_sendingProviderInput &&
      !_proposing;

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

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

      // A restart must not hide a pending approval or provider response. Task
      // history is best-effort here so an older Engine without history support
      // cannot prevent composing a new task.
      try {
        final recent = await client.listTasks(limit: 20);
        final pending = recent.where((task) =>
            task.status == 'accepted' ||
            task.status == 'exploring' ||
            task.status == 'waiting_for_approval' ||
            task.status == 'waiting_for_provider_input' ||
            task.status == 'running').firstOrNull;
        if (pending != null) {
          _lastSubmissionResult = await client.getTask(pending.taskId);
          _activePlan = _lastSubmissionResult?.plan;
          _activeProposal = _lastSubmissionResult?.proposal;
          _startPollingIfNeeded();
        }
      } catch (_) {
        // The visible Engine health/error state remains the source of truth;
        // history resumption is an enhancement, not a hidden fallback.
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
    if (mode == 'local_autopilot' && isCloudAssistedOnly) {
      _selectedMode = 'ask_before_changes';
      notifyListeners();
      return;
    }
    _selectedMode = mode;
    notifyListeners();
  }

  void setOffline(bool value) {
    // Cloud-assisted installs cannot satisfy Offline; keep the toggle honest.
    if (value && isCloudAssistedOnly) {
      _offline = false;
      notifyListeners();
      return;
    }
    _offline = value;
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

  void updateResolvePhrase(String text) {
    _resolvePhrase = text;
    notifyListeners();
  }

  Future<void> resolveNickname() async {
    final phrase = _resolvePhrase.trim();
    if (phrase.isEmpty) return;
    _resolving = true;
    _resolveMessage = null;
    _error = null;
    notifyListeners();
    try {
      final result = await client.resolveProject(phrase);
      if (result.matches.isEmpty) {
        _resolveMessage = 'No registered project matched "$phrase".';
      } else if (result.decisive) {
        final match = result.matches.first;
        EngineProject? found;
        for (final item in _projects) {
          if (item.projectId == match.projectId) {
            found = item;
            break;
          }
        }
        _selectedProject = found ??
            EngineProject(
              projectId: match.projectId,
              displayName: match.displayName,
              root: match.root,
              localAutopilotTrusted: false,
            );
        _resolveMessage =
            'Resolved to ${match.displayName} (score ${match.score.toStringAsFixed(2)}). Confirm before submitting.';
      } else {
        _resolveMessage =
            'Ambiguous: ${result.matches.map((m) => m.displayName).join(', ')}. Pick one from the list.';
      }
      _resolving = false;
      notifyListeners();
    } catch (e) {
      _resolving = false;
      _error = 'Project resolve failed: $e';
      notifyListeners();
    }
  }

  Future<bool> registerProject({
    required String displayName,
    required String root,
    bool localAutopilotTrusted = false,
  }) async {
    _registering = true;
    _error = null;
    notifyListeners();
    try {
      final project = await client.registerProject(
        displayName: displayName,
        root: root,
        localAutopilotTrusted: localAutopilotTrusted,
      );
      final existing = _projects.where((item) => item.projectId == project.projectId);
      if (existing.isEmpty) {
        _projects = [..._projects, project];
      }
      _selectedProject = project;
      _registering = false;
      _resolveMessage = 'Registered ${project.displayName}.';
      notifyListeners();
      return true;
    } catch (e) {
      _registering = false;
      _error = 'Failed to register project: $e';
      notifyListeners();
      return false;
    }
  }

  Future<EngineTaskStatus?> submitTask() async {
    if (!isValid) return null;

    _submitting = true;
    _error = null;
    _lastSubmissionResult = null;
    _activePlan = null;
    _activeProposal = null;
    notifyListeners();

    try {
      final submission = EngineTaskSubmission(
        request: _requestText.trim(),
        projectRoot: _selectedProject!.root,
        mode: _selectedMode,
        chatModel: _selectedChatModel!.name,
        builderModel: _selectedBuilderModel!.name,
        offline: _offline,
      );

      final result = await client.submitTask(submission);
      _lastSubmissionResult = result;
      _submitting = false;
      _lastAction = result.status == 'accepted'
          ? 'Task accepted. Draft an evidence plan, then prepare a proposal to review diffs.'
          : 'Task submitted.';
      _startPollingIfNeeded();
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
      _activeProposal = updatedStatus.proposal ?? _activeProposal;
      _startPollingIfNeeded();
      notifyListeners();
      return updatedStatus;
    } catch (e) {
      _error = 'Failed to refresh task status: $e';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskStatus?> prepareProposal() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty || !canPrepareProposal) {
      return null;
    }
    _proposing = true;
    _error = null;
    _lastAction = 'Contacting the builder to prepare a write proposal (no files will change yet)…';
    notifyListeners();
    try {
      final result = await client.proposeTask(currentId);
      _lastSubmissionResult = await client.getTask(result.taskId);
      _activeProposal = _lastSubmissionResult?.proposal;
      _proposing = false;
      _lastAction = _activeProposal == null
          ? 'Proposal preparation did not return a candidate.'
          : 'Proposal ready. Review the diffs, then approve the digest to apply writes.';
      _startPollingIfNeeded();
      notifyListeners();
      return _lastSubmissionResult;
    } catch (e) {
      _proposing = false;
      _error = 'Failed to prepare proposal: $e';
      _lastAction = 'Proposal preparation failed.';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskStatus?> approveActiveTask() async {
    final currentId = _lastSubmissionResult?.taskId;
    final digest = activeProposal?.digest;
    if (currentId == null ||
        currentId.isEmpty ||
        !isWaitingForApproval ||
        digest == null ||
        digest.isEmpty) {
      return null;
    }

    _approving = true;
    _error = null;
    _lastAction = 'Sending digest-bound approval to apply the proposal…';
    notifyListeners();

    try {
      final result = await client.approveTask(currentId, digest: digest);
      _lastSubmissionResult = await client.getTask(result.taskId);
      _approving = false;
      _lastAction = 'Engine accepted the approval. Applying the approved proposal…';
      _startPollingIfNeeded();
      notifyListeners();
      return _lastSubmissionResult;
    } catch (e) {
      _approving = false;
      _error = 'Task approval failed: $e';
      _lastAction = 'Approval request failed before the Engine accepted it.';
      notifyListeners();
      return null;
    }
  }

  List<String> get candidateFiles {
    if (_planDraftCandidates.isNotEmpty) return _planDraftCandidates;
    final err = _error ?? _lastSubmissionResult?.reason ?? '';
    if (err.contains('edit_plan_ambiguous:')) {
      final parts = err.split('edit_plan_ambiguous:');
      if (parts.length > 1) {
        return parts[1]
            .split(',')
            .map((e) => e.trim())
            .where((e) => e.isNotEmpty)
            .toList();
      }
    }
    return const [];
  }

  void applyCandidateFile(String candidatePath) {
    if (candidatePath.isEmpty) return;
    _requestText = '${_requestText.trim()} In file: $candidatePath';
    _error = null;
    _planDraftHint = null;
    _planDraftCandidates = const [];
    notifyListeners();
  }

  Future<EngineTaskPlan?> draftActivePlan() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty || !canDraftPlan) return null;
    _draftingPlan = true;
    _error = null;
    _planDraftHint = null;
    _planDraftCandidates = const [];
    notifyListeners();
    try {
      _activePlan = await client.draftTaskPlan(currentId);
      _draftingPlan = false;
      notifyListeners();
      return _activePlan;
    } on EngineApiException catch (e) {
      _draftingPlan = false;
      final reason = e.body['reason']?.toString() ?? e.message;
      final hint = e.body['hint']?.toString();
      final rawCandidates = e.body['candidates'];
      _planDraftCandidates = rawCandidates is List
          ? rawCandidates.map((c) => c.toString()).where((c) => c.isNotEmpty).toList()
          : const [];
      _planDraftHint = hint;
      _error = hint == null || hint.isEmpty
          ? 'Plan draft failed: $reason'
          : 'Plan draft failed: $reason\n$hint';
      notifyListeners();
      return null;
    } catch (e) {
      _draftingPlan = false;
      _error = 'Failed to draft evidence plan: $e';
      notifyListeners();
      return null;
    }
  }

  Future<EngineTaskStatus?> cancelActiveTask() async {
    final currentId = _lastSubmissionResult?.taskId;
    if (currentId == null || currentId.isEmpty || !canCancelActiveTask) {
      return null;
    }
    _canceling = true;
    _error = null;
    notifyListeners();
    try {
      _lastSubmissionResult = await client.cancelTask(currentId);
      _activePlan = null;
      _activeProposal = null;
      _canceling = false;
      _stopPolling();
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
      _startPollingIfNeeded();
      notifyListeners();
      return _lastSubmissionResult;
    } catch (e) {
      _sendingProviderInput = false;
      _error = 'Failed to send provider input: $e';
      notifyListeners();
      return null;
    }
  }

  void _startPollingIfNeeded() {
    final status = _lastSubmissionResult?.status;
    final active = status == 'accepted' ||
        status == 'exploring' ||
        status == 'waiting_for_approval' ||
        status == 'waiting_for_provider_input' ||
        status == 'running';
    if (!active) {
      _stopPolling();
      return;
    }
    _pollTimer ??= Timer.periodic(const Duration(seconds: 2), (_) {
      unawaited(refreshTaskStatus());
    });
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }
}
