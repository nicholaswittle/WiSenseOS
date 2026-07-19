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

class EngineTaskSubmission {
  const EngineTaskSubmission({
    required this.request,
    required this.projectRoot,
    required this.mode,
    required this.chatModel,
    required this.builderModel,
  });

  final String request;
  final String projectRoot;
  final String mode;
  final String chatModel;
  final String builderModel;

  Map<String, dynamic> toJson() => {
        'request': request,
        'project_root': projectRoot,
        'mode': mode,
        'chat_model': chatModel,
        'builder_model': builderModel,
      };
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

class EngineTaskStatus {
  const EngineTaskStatus({
    required this.taskId,
    required this.status,
    required this.statusCode,
    required this.reason,
    required this.events,
  });

  final String taskId;
  final String status;
  final int statusCode;
  final String? reason;
  final List<EngineTaskEvent> events;

  bool get isBlocked => statusCode == 409 || status == 'blocked';

  factory EngineTaskStatus.fromJson(
    Map<String, dynamic> json, {
    required int statusCode,
  }) {
    final rawEvents = (json['events'] as List?) ?? const [];
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
    );
  }
}
