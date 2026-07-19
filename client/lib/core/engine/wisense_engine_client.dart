import 'dart:convert';

import 'package:http/http.dart' as http;

import 'engine_models.dart';

class WiSenseEngineClient {
  WiSenseEngineClient({
    Uri? baseUri,
    http.Client? client,
    this.tokenProvider,
  })  : _baseUri = baseUri ?? Uri.parse('http://127.0.0.1:5050'),
        _client = client ?? http.Client();

  final Uri _baseUri;
  final http.Client _client;
  final Future<String?> Function()? tokenProvider;

  Future<EngineHealth> health() async {
    final response = await _client.get(
      _endpoint('/api/v1/health'),
      headers: await _headers(),
    );
    final body = _body(response);
    _requireSuccess(response, body, 'Health check');
    return EngineHealth.fromJson(body);
  }

  Future<List<EngineModelProfile>> listModels() async {
    final response = await _client.get(
      _endpoint('/api/v1/models'),
      headers: await _headers(),
    );
    final body = _body(response);
    _requireSuccess(response, body, 'List models');
    return ((body['models'] as List?) ?? const [])
        .whereType<Map>()
        .map((profile) =>
            EngineModelProfile.fromJson(Map<String, dynamic>.from(profile)))
        .toList(growable: false);
  }

  Future<List<EngineProject>> listProjects() async {
    final response = await _client.get(
      _endpoint('/api/v1/projects'),
      headers: await _headers(),
    );
    final body = _body(response);
    _requireSuccess(response, body, 'List projects');
    return ((body['projects'] as List?) ?? const [])
        .whereType<Map>()
        .map((project) =>
            EngineProject.fromJson(Map<String, dynamic>.from(project)))
        .toList(growable: false);
  }

  Future<EngineProject> registerProject({
    required String displayName,
    required String root,
    bool localAutopilotTrusted = false,
  }) async {
    final response = await _client.post(
      _endpoint('/api/v1/projects'),
      headers: await _headers(),
      body: jsonEncode({
        'display_name': displayName,
        'root': root,
        'local_autopilot_trusted': localAutopilotTrusted,
      }),
    );
    final body = _body(response);
    _requireSuccess(response, body, 'Register project');
    return EngineProject.fromJson(body);
  }

  Future<EngineTaskStatus> submitTask(EngineTaskSubmission submission) async {
    final response = await _client.post(
      _endpoint('/api/v1/tasks'),
      headers: await _headers(),
      body: jsonEncode(submission.toJson()),
    );
    final body = _body(response);
    if (response.statusCode == 202 || response.statusCode == 409) {
      return EngineTaskStatus.fromJson(body, statusCode: response.statusCode);
    }
    _requireSuccess(response, body, 'Submit task');
    return EngineTaskStatus.fromJson(body, statusCode: response.statusCode);
  }

  Future<EngineTaskStatus> getTask(String taskId) async {
    final response = await _client.get(
      _endpoint('/api/v1/tasks/$taskId'),
      headers: await _headers(),
    );
    final body = _body(response);
    _requireSuccess(response, body, 'Get task');
    return EngineTaskStatus.fromJson(body, statusCode: response.statusCode);
  }

  Uri _endpoint(String path) =>
      _baseUri.resolve(path.startsWith('/') ? path.substring(1) : path);

  Future<Map<String, String>> _headers() async {
    final headers = <String, String>{'Accept': 'application/json'};
    final token = await tokenProvider?.call();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Map<String, dynamic> _body(http.Response response) {
    if (response.body.isEmpty) return const {};
    final decoded = jsonDecode(response.body);
    if (decoded is Map) return Map<String, dynamic>.from(decoded);
    throw EngineApiException(
      statusCode: response.statusCode,
      message: 'Engine returned a non-object JSON body',
      body: const {},
    );
  }

  void _requireSuccess(
      http.Response response, Map<String, dynamic> body, String action) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw EngineApiException(
      statusCode: response.statusCode,
      message: '$action failed with status ${response.statusCode}',
      body: body,
    );
  }
}
