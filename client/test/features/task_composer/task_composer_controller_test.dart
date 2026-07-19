import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/engine_models.dart';
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';
import 'package:wisense_os_client/features/task_composer/task_composer_controller.dart';

class FakeHttpClient extends http.BaseClient {
  FakeHttpClient(this.handler);

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
  group('TaskComposerController', () {
    test('load() fetches projects and model profiles and sets defaults', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/projects')) {
          return http.Response(
            jsonEncode({
              'projects': [
                {
                  'project_id': 'proj-1',
                  'display_name': 'Billing System',
                  'root': 'C:/development/projects/billing',
                  'local_autopilot_trusted': true,
                }
              ]
            }),
            200,
          );
        } else if (request.url.path.endsWith('/models')) {
          return http.Response(
            jsonEncode({
              'models': [
                {
                  'name': 'qwen2.5-coder:7b',
                  'provider': 'ollama',
                  'roles': ['builder', 'chat'],
                  'available': true,
                  'supervised_testing_only': false,
                  'future_local_target': false,
                },
                {
                  'name': 'claude-3-7-sonnet',
                  'provider': 'anthropic',
                  'roles': ['planner'],
                  'available': true,
                  'supervised_testing_only': true,
                  'future_local_target': false,
                }
              ]
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskComposerController(client: engineClient);

      await controller.load();

      expect(controller.projects.length, equals(1));
      expect(controller.projects.first.displayName, equals('Billing System'));
      expect(controller.selectedProject, equals(controller.projects.first));
      expect(controller.models.length, equals(2));
      expect(controller.selectedChatModel, isNotNull);
      expect(controller.selectedBuilderModel, isNotNull);
    });

    test('cloud-Autopilot refusal blocks validation in UI controller', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(jsonEncode({'projects': [], 'models': []}), 200);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskComposerController(client: engineClient);

      const cloudModel = EngineModelProfile(
        name: 'claude-3-7-sonnet',
        provider: 'anthropic',
        roles: ['builder'],
        available: true,
        supervisedTestingOnly: true,
        futureLocalTarget: false,
      );

      const project = EngineProject(
        projectId: 'proj-1',
        displayName: 'Billing',
        root: 'C:/proj',
        localAutopilotTrusted: false,
      );

      controller.selectProject(project);
      controller.selectChatModel(cloudModel);
      controller.selectBuilderModel(cloudModel);
      controller.selectMode('local_autopilot');
      controller.updateRequestText('Perform live autopilot refactor');

      expect(controller.isCloudBuilderSelected, isTrue);
      expect(controller.isAutopilotBlockedByCloud, isTrue);
      expect(controller.isValid, isFalse);
      expect(
        controller.autopilotBlockedReason,
        contains('Local Autopilot is disabled when using a cloud builder model'),
      );

      final result = await controller.submitTask();
      expect(result, isNull);
    });

    test('submitTask() creates valid payload and handles 202 Accepted', () async {
      late http.BaseRequest capturedRequest;
      late String capturedBody;

      final fakeClient = FakeHttpClient((request) async {
        capturedRequest = request;
        if (request is http.Request) {
          capturedBody = request.body;
        }
        return http.Response(
          jsonEncode({'task_id': 'task-101', 'status': 'accepted'}),
          202,
        );
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskComposerController(client: engineClient);

      const localModel = EngineModelProfile(
        name: 'qwen2.5-coder:7b',
        provider: 'ollama',
        roles: ['builder', 'chat'],
        available: true,
        supervisedTestingOnly: false,
        futureLocalTarget: false,
      );

      const project = EngineProject(
        projectId: 'proj-1',
        displayName: 'Billing System',
        root: 'C:/development/projects/billing',
        localAutopilotTrusted: true,
      );

      controller.selectProject(project);
      controller.selectChatModel(localModel);
      controller.selectBuilderModel(localModel);
      controller.selectMode('ask_before_changes');
      controller.updateRequestText('Fix tax calculation logic');

      expect(controller.isValid, isTrue);

      final status = await controller.submitTask();

      expect(capturedRequest.method, equals('POST'));
      expect(capturedRequest.url.path, equals('/api/v1/tasks'));

      final bodyJson = jsonDecode(capturedBody) as Map<String, dynamic>;
      expect(bodyJson['request'], equals('Fix tax calculation logic'));
      expect(bodyJson['project_root'], equals('C:/development/projects/billing'));
      expect(bodyJson['mode'], equals('ask_before_changes'));
      expect(bodyJson['chat_model'], equals('qwen2.5-coder:7b'));
      expect(bodyJson['builder_model'], equals('qwen2.5-coder:7b'));

      expect(status, isNotNull);
      expect(status!.statusCode, equals(202));
      expect(status.status, equals('accepted'));
      expect(status.isBlocked, isFalse);
    });

    test('submitTask() handles 409 Conflict structured blocked status', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(
          jsonEncode({
            'task_id': 'task-102',
            'status': 'dispatch_busy',
            'reason': 'Lock held by running background task',
          }),
          409,
        );
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskComposerController(client: engineClient);

      const localModel = EngineModelProfile(
        name: 'qwen2.5-coder:7b',
        provider: 'ollama',
        roles: ['builder'],
        available: true,
        supervisedTestingOnly: false,
        futureLocalTarget: false,
      );

      const project = EngineProject(
        projectId: 'proj-1',
        displayName: 'Billing',
        root: 'C:/proj',
        localAutopilotTrusted: true,
      );

      controller.selectProject(project);
      controller.selectChatModel(localModel);
      controller.selectBuilderModel(localModel);
      controller.selectMode('ask_before_changes');
      controller.updateRequestText('Fix bug');

      final status = await controller.submitTask();

      expect(status, isNotNull);
      expect(status!.statusCode, equals(409));
      expect(status.isBlocked, isTrue);
      expect(status.reason, equals('Lock held by running background task'));
    });
  });
}
