import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/engine_models.dart';
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';

class FakeClient extends http.BaseClient {
  FakeClient(this.handler);
  final Future<http.Response> Function(http.BaseRequest request) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final response = await handler(request);
    return http.StreamedResponse(
      Stream.value(utf8.encode(response.body)),
      response.statusCode,
      headers: response.headers,
      request: request,
    );
  }
}

void main() {
  test('health reads the real engine shape and sends optional auth', () async {
    late http.BaseRequest captured;
    final client = WiSenseEngineClient(
      client: FakeClient((request) async {
        captured = request;
        return http.Response(jsonEncode({
          'engine': 'wisense-os', 'status': 'ready', 'version': '0.1.0',
        }), 200);
      }),
      tokenProvider: () async => 'test-token',
    );

    final health = await client.health();
    expect(captured.url.path, '/api/v1/health');
    expect(captured.headers['Authorization'], 'Bearer test-token');
    expect(health.status, 'ready');
  });

  test('listModels parses cloud profiles without treating them as local', () async {
    final client = WiSenseEngineClient(client: FakeClient((_) async => http.Response(jsonEncode({
      'models': [{
        'name': 'gemma4:31b-cloud', 'provider': 'cloud', 'roles': ['builder'],
        'available': true, 'supervised_testing_only': true, 'future_local_target': true,
      }],
    }), 200)));

    final models = await client.listModels();
    expect(models.single.provider, 'cloud');
    expect(models.single.futureLocalTarget, isTrue);
  });

  test('submitTask preserves its contract and accepts 202', () async {
    late String requestBody;
    final client = WiSenseEngineClient(client: FakeClient((request) async {
      requestBody = (request as http.Request).body;
      return http.Response(jsonEncode({'task_id': 'task-1', 'status': 'accepted'}), 202);
    }));
    final result = await client.submitTask(const EngineTaskSubmission(
      request: 'Fix totals', projectRoot: r'C:\demo', mode: 'ask_before_changes',
      chatModel: 'glm-5.2:cloud', builderModel: 'gemma4:31b-cloud',
    ));

    expect(jsonDecode(requestBody)['builder_model'], 'gemma4:31b-cloud');
    expect(result.status, 'accepted');
  });

  test('409 is a structured blocked task rather than an exception', () async {
    final client = WiSenseEngineClient(client: FakeClient((_) async => http.Response(jsonEncode({
      'task_id': 'task-2', 'status': 'blocked', 'reason': 'no qualified local builder',
    }), 409)));
    final result = await client.submitTask(const EngineTaskSubmission(
      request: 'Fix totals', projectRoot: r'C:\demo', mode: 'local_autopilot',
      chatModel: 'glm-5.2:cloud', builderModel: 'gemma4:31b-cloud',
    ));

    expect(result.isBlocked, isTrue);
    expect(result.reason, contains('local builder'));
  });

  test('task status parses the durable event shape', () async {
    final client = WiSenseEngineClient(client: FakeClient((_) async => http.Response(jsonEncode({
      'task_id': 'task-3', 'status': 'running',
      'events': [{'sequence': 1, 'kind': 'accepted', 'detail': 'task persisted'}],
    }), 200)));
    final result = await client.getTask('task-3');

    expect(result.events.single.kind, 'accepted');
    expect(result.events.single.sequence, 1);
  });

  test('listTasks reads persisted task summaries for restart recovery', () async {
    late http.BaseRequest captured;
    final client = WiSenseEngineClient(client: FakeClient((request) async {
      captured = request;
      return http.Response(jsonEncode({
        'tasks': [{'task_id': 'task-pending', 'status': 'waiting_for_approval'}],
      }), 200);
    }));

    final tasks = await client.listTasks(limit: 20);

    expect(captured.url.path, '/api/v1/tasks');
    expect(captured.url.queryParameters['limit'], '20');
    expect(tasks.single.taskId, 'task-pending');
  });

  test('draftTaskPlan reads the durable evidence plan contract', () async {
    late http.BaseRequest captured;
    final client = WiSenseEngineClient(client: FakeClient((request) async {
      captured = request;
      return http.Response(jsonEncode({
        'ok': true,
        'task_id': 'task-4',
        'plan': {
          'title': 'Add GET /api/v1/version',
          'summary': 'Extend the existing API and fixture.',
          'files': ['wisense_os/api.py', 'tests/test_bootstrap.py'],
          'api_contract': ['GET /api/v1/version returns JSON.'],
          'acceptance': ['The existing fixture verifies the route.'],
          'source': 'evidence',
        },
      }), 200);
    }));

    final plan = await client.draftTaskPlan('task-4');

    expect(captured.method, 'POST');
    expect(captured.url.path, '/api/v1/tasks/task-4/plan-draft');
    expect(plan.files, ['wisense_os/api.py', 'tests/test_bootstrap.py']);
    expect(plan.source, 'evidence');
  });

  test('cancelTask posts only to the task cancellation route', () async {
    late http.BaseRequest captured;
    final client = WiSenseEngineClient(client: FakeClient((request) async {
      captured = request;
      return http.Response(jsonEncode({'task_id': 'task-5', 'status': 'canceled'}), 200);
    }));

    final status = await client.cancelTask('task-5');

    expect(captured.method, 'POST');
    expect(captured.url.path, '/api/v1/tasks/task-5/cancel');
    expect(status.status, 'canceled');
  });

  test('non-success response throws EngineApiException', () async {
    final client = WiSenseEngineClient(client: FakeClient((_) async =>
        http.Response(jsonEncode({'error': 'bad engine'}), 500)));

    expect(client.health(), throwsA(isA<EngineApiException>()));
  });
}
