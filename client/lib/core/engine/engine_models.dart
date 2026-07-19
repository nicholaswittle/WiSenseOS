class EngineApiException implements Exception {
  const EngineApiException({
    required this.statusCode,
    required this.message,
    required this.body,
  });

  final int statusCode;
  final String message;
  final Map<String, dynamic> body;
}

class EngineHealth {
  const EngineHealth({
    required this.engine,
    required this.status,
    required this.version,
  });

  final String engine;
  final String status;
  final String version;

  factory EngineHealth.fromJson(Map<String, dynamic> json) => EngineHealth(
        engine: json['engine']?.toString() ?? '',
        status: json['status']?.toString() ?? 'unknown',
        version: json['version']?.toString() ?? '',
      );
}

class EngineDiagnostics {
  const EngineDiagnostics({
    required this.ollamaReachable,
    required this.gitAvailable,
    required this.cloudAssistedOnly,
    required this.modelsRuntime,
    required this.notes,
    this.engineVersion = '',
  });

  final bool ollamaReachable;
  final bool gitAvailable;
  final bool cloudAssistedOnly;
  final List<String> modelsRuntime;
  final List<String> notes;
  final String engineVersion;

  factory EngineDiagnostics.fromJson(Map<String, dynamic> json) {
    final engine = json['engine'] is Map
        ? Map<String, dynamic>.from(json['engine'] as Map)
        : const <String, dynamic>{};
    return EngineDiagnostics(
      ollamaReachable: json['ollama_reachable'] == true,
      gitAvailable: json['git_available'] == true,
      cloudAssistedOnly: json['cloud_assisted_only'] == true,
      modelsRuntime: ((json['models_runtime'] as List?) ?? const [])
          .map((item) => item.toString())
          .toList(growable: false),
      notes: ((json['notes'] as List?) ?? const [])
          .map((item) => item.toString())
          .toList(growable: false),
      engineVersion: engine['version']?.toString() ?? '',
    );
  }
}

class EngineModelProfile {
  const EngineModelProfile({
    required this.name,
    required this.provider,
    required this.roles,
    required this.available,
    required this.supervisedTestingOnly,
    required this.futureLocalTarget,
  });

  final String name;
  final String provider;
  final List<String> roles;
  final bool available;
  final bool supervisedTestingOnly;
  final bool futureLocalTarget;

  bool get isCloud =>
      provider.isNotEmpty && provider != 'local' && provider != 'ollama';

  factory EngineModelProfile.fromJson(Map<String, dynamic> json) =>
      EngineModelProfile(
        name: json['name']?.toString() ?? '',
        provider: json['provider']?.toString() ?? '',
        roles: ((json['roles'] as List?) ?? const [])
            .map((role) => role.toString())
            .toList(growable: false),
        available: json['available'] == true,
        supervisedTestingOnly: json['supervised_testing_only'] == true,
        futureLocalTarget: json['future_local_target'] == true,
      );
}

class EngineProject {
  const EngineProject({
    required this.projectId,
    required this.displayName,
    required this.root,
    required this.localAutopilotTrusted,
  });

  final String projectId;
  final String displayName;
  final String root;
  final bool localAutopilotTrusted;

  factory EngineProject.fromJson(Map<String, dynamic> json) => EngineProject(
        projectId: json['project_id']?.toString() ?? json['id']?.toString() ?? '',
        displayName: json['display_name']?.toString() ?? json['name']?.toString() ?? '',
        root: json['root']?.toString() ?? json['root_path']?.toString() ?? '',
        localAutopilotTrusted: json['local_autopilot_trusted'] == true,
      );

  Map<String, dynamic> toJson() => {
        'display_name': displayName,
        'root': root,
        'local_autopilot_trusted': localAutopilotTrusted,
      };
}

class EngineProjectMatch {
  const EngineProjectMatch({
    required this.projectId,
    required this.displayName,
    required this.root,
    required this.score,
  });

  final String projectId;
  final String displayName;
  final String root;
  final double score;

  factory EngineProjectMatch.fromJson(Map<String, dynamic> json) =>
      EngineProjectMatch(
        projectId: json['project_id']?.toString() ?? '',
        displayName: json['display_name']?.toString() ?? '',
        root: json['root']?.toString() ?? '',
        score: (json['score'] as num?)?.toDouble() ?? 0,
      );
}

class EngineProjectResolveResult {
  const EngineProjectResolveResult({
    required this.phrase,
    required this.decisive,
    required this.matches,
  });

  final String phrase;
  final bool decisive;
  final List<EngineProjectMatch> matches;

  factory EngineProjectResolveResult.fromJson(Map<String, dynamic> json) =>
      EngineProjectResolveResult(
        phrase: json['phrase']?.toString() ?? '',
        decisive: json['decisive'] == true,
        matches: ((json['matches'] as List?) ?? const [])
            .whereType<Map>()
            .map((item) =>
                EngineProjectMatch.fromJson(Map<String, dynamic>.from(item)))
            .toList(growable: false),
      );
}

class EngineTaskSubmission {
  const EngineTaskSubmission({
    required this.request,
    required this.projectRoot,
    required this.mode,
    required this.chatModel,
    required this.builderModel,
    this.offline = false,
  });

  final String request;
  final String projectRoot;
  final String mode;
  final String chatModel;
  final String builderModel;
  final bool offline;

  Map<String, dynamic> toJson() => {
        'request': request,
        'project_root': projectRoot,
        'mode': mode,
        'chat_model': chatModel,
        'builder_model': builderModel,
        'offline': offline,
      };
}

class EngineTaskProposal {
  const EngineTaskProposal({
    required this.digest,
    required this.summary,
    required this.diffs,
    required this.files,
  });

  final String digest;
  final String summary;
  final Map<String, String> diffs;
  final List<String> files;

  factory EngineTaskProposal.fromJson(Map<String, dynamic> json) {
    final rawDiffs = json['diffs'];
    final diffs = <String, String>{};
    if (rawDiffs is Map) {
      rawDiffs.forEach((key, value) {
        diffs[key.toString()] = value?.toString() ?? '';
      });
    }
    final rawFiles = json['files'];
    final files = rawFiles is List
        ? rawFiles.map((item) => item.toString()).toList(growable: false)
        : diffs.keys.toList(growable: false);
    return EngineTaskProposal(
      digest: json['digest']?.toString() ?? '',
      summary: json['summary']?.toString() ?? '',
      diffs: diffs,
      files: files,
    );
  }
}

class EngineTaskEvent {
  const EngineTaskEvent({
    required this.sequence,
    required this.kind,
    required this.detail,
  });

  final int sequence;
  final String kind;
  final String detail;

  factory EngineTaskEvent.fromJson(Map<String, dynamic> json) =>
      EngineTaskEvent(
        sequence: (json['sequence'] as num?)?.toInt() ?? 0,
        kind: json['kind']?.toString() ?? 'event',
        detail: json['detail']?.toString() ?? '',
      );
}

class EngineTaskPlan {
  const EngineTaskPlan({
    required this.title,
    required this.summary,
    required this.files,
    required this.apiContract,
    required this.acceptance,
    required this.source,
  });

  final String title;
  final String summary;
  final List<String> files;
  final List<String> apiContract;
  final List<String> acceptance;
  final String source;

  factory EngineTaskPlan.fromJson(Map<String, dynamic> json) => EngineTaskPlan(
        title: json['title']?.toString() ?? '',
        summary: json['summary']?.toString() ?? '',
        files: ((json['files'] as List?) ?? const []).map((item) => item.toString()).toList(growable: false),
        apiContract: ((json['api_contract'] as List?) ?? const []).map((item) => item.toString()).toList(growable: false),
        acceptance: ((json['acceptance'] as List?) ?? const []).map((item) => item.toString()).toList(growable: false),
        source: json['source']?.toString() ?? '',
      );
}

class EngineTaskStatus {
  const EngineTaskStatus({
    required this.taskId,
    required this.status,
    required this.statusCode,
    required this.reason,
    required this.events,
    this.plan,
    this.proposal,
    this.requestText = '',
    this.mode = '',
    this.builderModel = '',
    this.chatModel = '',
    this.projectRoot = '',
  });

  final String taskId;
  final String status;
  final int statusCode;
  final String? reason;
  final List<EngineTaskEvent> events;
  final EngineTaskPlan? plan;
  final EngineTaskProposal? proposal;
  final String requestText;
  final String mode;
  final String builderModel;
  final String chatModel;
  final String projectRoot;

  bool get isBlocked => statusCode == 409 || status == 'blocked';

  bool get isActive =>
      status == 'accepted' ||
      status == 'exploring' ||
      status == 'waiting_for_approval' ||
      status == 'waiting_for_provider_input' ||
      status == 'running';

  factory EngineTaskStatus.fromJson(
    Map<String, dynamic> json, {
    required int statusCode,
  }) {
    final rawEvents = (json['events'] as List?) ?? const [];
    final request = json['request'] is Map
        ? Map<String, dynamic>.from(json['request'] as Map)
        : const <String, dynamic>{};
    return EngineTaskStatus(
      taskId: json['task_id']?.toString() ?? '',
      status: json['status']?.toString() ??
          (statusCode == 202 ? 'accepted' : 'unknown'),
      statusCode: statusCode,
      reason: json['reason']?.toString(),
      events: rawEvents
          .whereType<Map>()
          .map((event) => EngineTaskEvent.fromJson(
              Map<String, dynamic>.from(event)))
          .toList(growable: false),
      plan: json['plan'] is Map
          ? EngineTaskPlan.fromJson(Map<String, dynamic>.from(json['plan'] as Map))
          : null,
      proposal: json['proposal'] is Map
          ? EngineTaskProposal.fromJson(
              Map<String, dynamic>.from(json['proposal'] as Map))
          : null,
      requestText: request['request']?.toString() ?? '',
      mode: request['mode']?.toString() ?? '',
      builderModel: request['builder_model']?.toString() ?? '',
      chatModel: request['chat_model']?.toString() ?? '',
      projectRoot: request['project_root']?.toString() ?? '',
    );
  }
}

class EngineComputeTelemetry {
  const EngineComputeTelemetry({
    required this.vramUsedMb,
    required this.vramTotalMb,
    required this.tokensPerSec,
    required this.activeLocalRuns,
    required this.activeCloudRuns,
    required this.instrumented,
  });

  final int? vramUsedMb;
  final int? vramTotalMb;
  final double? tokensPerSec;
  final int activeLocalRuns;
  final int activeCloudRuns;
  final bool instrumented;

  factory EngineComputeTelemetry.fromJson(Map<String, dynamic> json) =>
      EngineComputeTelemetry(
        vramUsedMb: (json['vram_used_mb'] as num?)?.toInt(),
        vramTotalMb: (json['vram_total_mb'] as num?)?.toInt(),
        tokensPerSec: (json['tokens_per_sec'] as num?)?.toDouble(),
        activeLocalRuns: (json['active_local_runs'] as num?)?.toInt() ?? 0,
        activeCloudRuns: (json['active_cloud_runs'] as num?)?.toInt() ?? 0,
        instrumented: json['instrumented'] == true,
      );
}

class EngineIntent {
  const EngineIntent({
    required this.kind,
    this.targetFile,
    this.reason = '',
    this.source = 'floor',
  });

  final String kind;
  final String? targetFile;
  final String reason;
  final String source;

  factory EngineIntent.fromJson(Map<String, dynamic> json) => EngineIntent(
        kind: json['kind']?.toString() ?? 'chat',
        targetFile: json['target_file']?.toString(),
        reason: json['reason']?.toString() ?? '',
        source: json['source']?.toString() ?? 'floor',
      );
}

class EngineQualificationScore {
  const EngineQualificationScore({
    required this.name,
    required this.score,
    required this.status,
    this.detail = '',
  });

  final String name;
  final double? score;
  final String status;
  final String detail;

  factory EngineQualificationScore.fromJson(Map<String, dynamic> json) =>
      EngineQualificationScore(
        name: json['name']?.toString() ?? json['model']?.toString() ?? '',
        score: (json['score'] as num?)?.toDouble(),
        status: json['status']?.toString() ?? 'unevaluated',
        detail: json['detail']?.toString() ?? '',
      );
}

class EngineBudgetSnapshot {
  const EngineBudgetSnapshot({
    required this.capUsd,
    required this.confirmedUsd,
    required this.reservedUsd,
    required this.exposureUsd,
  });

  final double capUsd;
  final double confirmedUsd;
  final double reservedUsd;
  final double exposureUsd;

  factory EngineBudgetSnapshot.fromJson(Map<String, dynamic> json) =>
      EngineBudgetSnapshot(
        capUsd: (json['cap_usd'] as num?)?.toDouble() ?? 0,
        confirmedUsd: (json['confirmed_usd'] as num?)?.toDouble() ?? 0,
        reservedUsd: (json['reserved_usd'] as num?)?.toDouble() ?? 0,
        exposureUsd: (json['exposure_usd'] as num?)?.toDouble() ?? 0,
      );
}

class EngineTelemetryReport {
  const EngineTelemetryReport({
    required this.compute,
    required this.qualification,
    this.budget,
  });

  final EngineComputeTelemetry compute;
  final List<EngineQualificationScore> qualification;
  final EngineBudgetSnapshot? budget;

  factory EngineTelemetryReport.fromJson(Map<String, dynamic> json) {
    final rawCompute = json['compute'] is Map ? json['compute'] as Map<String, dynamic> : <String, dynamic>{};
    final rawQual = (json['qualification'] as List?) ?? const [];
    return EngineTelemetryReport(
      compute: EngineComputeTelemetry.fromJson(rawCompute),
      qualification: rawQual
          .whereType<Map>()
          .map((item) => EngineQualificationScore.fromJson(Map<String, dynamic>.from(item)))
          .toList(growable: false),
      budget: json['budget'] is Map
          ? EngineBudgetSnapshot.fromJson(
              Map<String, dynamic>.from(json['budget'] as Map))
          : null,
    );
  }
}

class EngineSOPWorkflow {
  const EngineSOPWorkflow({
    required this.id,
    required this.name,
    required this.category,
    required this.description,
    required this.defaultRequest,
    required this.recommendedMode,
  });

  final String id;
  final String name;
  final String category;
  final String description;
  final String defaultRequest;
  final String recommendedMode;

  factory EngineSOPWorkflow.fromJson(Map<String, dynamic> json) => EngineSOPWorkflow(
        id: json['id']?.toString() ?? '',
        name: json['name']?.toString() ?? '',
        category: json['category']?.toString() ?? '',
        description: json['description']?.toString() ?? '',
        defaultRequest: json['default_request']?.toString() ?? '',
        recommendedMode: json['recommended_mode']?.toString() ?? 'ask_before_changes',
      );
}

class EngineRouteRecommendation {
  const EngineRouteRecommendation({
    required this.chatModel,
    required this.builderModel,
    required this.complexity,
    required this.reason,
    required this.estimatedCost,
  });

  final String chatModel;
  final String builderModel;
  final String complexity;
  final String reason;
  final double estimatedCost;

  factory EngineRouteRecommendation.fromJson(Map<String, dynamic> json) =>
      EngineRouteRecommendation(
        chatModel: json['chat_model']?.toString() ?? '',
        builderModel: json['builder_model']?.toString() ?? '',
        complexity: json['complexity']?.toString() ?? 'low',
        reason: json['reason']?.toString() ?? '',
        estimatedCost: (json['estimated_cost'] as num?)?.toDouble() ?? 0.0,
      );
}
