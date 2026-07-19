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
  group('TaskComposerController & Approval Flow', () {
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
                  'roles': ['planner', 'builder'],
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

    test('submitTask() creates valid payload and DOES NOT automatically approve', () async {
      final requestedUrls = <String>[];
      final fakeClient = FakeHttpClient((request) async {
        requestedUrls.add(request.url.path);
        return http.Response(
          jsonEncode({
            'task_id': 'task-101',
            'status': 'waiting_for_approval',
            'events': [
              {
                'sequence': 1,
                'kind': 'proposal_ready',
                'detail': 'Proposal generated and waiting for approval',
              }
            ]
          }),
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

      final status = await controller.submitTask();

      // Verify POST /api/v1/tasks was called, but /approve was NOT called automatically
      expect(requestedUrls, contains('/api/v1/tasks'));
      expect(requestedUrls.any((url) => url.contains('/approve')), isFalse);

      expect(status, isNotNull);
      expect(status!.taskId, equals('task-101'));
      expect(status.status, equals('waiting_for_approval'));
      expect(controller.isWaitingForApproval, isTrue);
      expect(controller.showCloudApprovalWarning, isFalse);
      expect(status.events.length, equals(1));
      expect(status.events.first.sequence, equals(1));
      expect(status.events.first.kind, equals('proposal_ready'));
      expect(status.events.first.detail, contains('waiting for approval'));
    });

    test('approveActiveTask() sends POST then reloads the durable event timeline', () async {
      late http.BaseRequest approveRequest;
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/approve')) {
          approveRequest = request;
          return http.Response(
            jsonEncode({
              'task_id': 'task-101',
              'status': 'running',
            }),
            202,
          );
        }
        if (request.url.path.endsWith('/tasks/task-101')) {
          return http.Response(
            jsonEncode({
              'task_id': 'task-101',
              'status': 'running',
              'events': [
                {'sequence': 1, 'kind': 'proposal_ready', 'detail': 'Proposal generated'},
                {'sequence': 2, 'kind': 'approved', 'detail': 'User approved handoff'},
              ],
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'task_id': 'task-101',
            'status': 'waiting_for_approval',
          }),
          202,
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

      await controller.submitTask();
      expect(controller.isWaitingForApproval, isTrue);

      final approvedStatus = await controller.approveActiveTask();

      expect(approveRequest.method, equals('POST'));
      expect(approveRequest.url.path, equals('/api/v1/tasks/task-101/approve'));

      expect(approvedStatus, isNotNull);
      expect(approvedStatus!.status, equals('running'));
      expect(controller.isWaitingForApproval, isFalse);
      expect(approvedStatus.events.length, equals(2));
      expect(approvedStatus.events[1].kind, equals('approved'));
    });

    test('cloud warning flag activates when waiting for approval with cloud builder model', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(
          jsonEncode({
            'task_id': 'task-102',
            'status': 'waiting_for_approval',
          }),
          202,
        );
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
      controller.selectMode('ask_before_changes');
      controller.updateRequestText('Audit security');

      await controller.submitTask();

      expect(controller.isWaitingForApproval, isTrue);
      expect(controller.isCloudBuilderSelected, isTrue);
      expect(controller.showCloudApprovalWarning, isTrue);
    });

    test('provider follow-up requires explicit input and reloads its durable timeline', () async {
      String? sentMessage;
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/provider-input')) {
          sentMessage = jsonDecode((request as http.Request).body)['message'] as String;
          return http.Response(jsonEncode({'task_id': 'task-103', 'status': 'running'}), 202);
        }
        if (request.url.path.endsWith('/tasks/task-103')) {
          return http.Response(jsonEncode({
            'task_id': 'task-103',
            'status': 'completed',
            'events': [
              {'sequence': 1, 'kind': 'provider_input_required', 'detail': 'Work Center requires an explicit user response'},
              {'sequence': 2, 'kind': 'provider_input_submitted', 'detail': 'user sent response'},
              {'sequence': 3, 'kind': 'completed', 'detail': 'engine response recorded'},
            ],
          }), 200);
        }
        return http.Response(jsonEncode({
          'task_id': 'task-103',
          'status': 'waiting_for_provider_input',
          'reason': 'This may spend quota -- go ahead?',
        }), 202);
      });
      final controller = TaskComposerController(client: WiSenseEngineClient(client: fakeClient));
      const model = EngineModelProfile(
        name: 'gemma4:31b-cloud', provider: 'cloud', roles: ['builder', 'chat'],
        available: true, supervisedTestingOnly: true, futureLocalTarget: true,
      );
      const project = EngineProject(
        projectId: 'proj-1', displayName: 'WiSense', root: 'C:/wisense', localAutopilotTrusted: false,
      );
      controller.selectProject(project);
      controller.selectChatModel(model);
      controller.selectBuilderModel(model);
      controller.updateRequestText('Add endpoint');

      await controller.submitTask();

      expect(controller.isWaitingForProviderInput, isTrue);
      expect(controller.isValid, isFalse);
      expect(await controller.sendProviderInput(), isNull);
      controller.updateProviderInputText('go ahead');
      final result = await controller.sendProviderInput();

      expect(sentMessage, 'go ahead');
      expect(result!.status, 'completed');
      expect(result.events.last.kind, 'completed');
      expect(controller.providerInputText, isEmpty);
    });
  });
}
