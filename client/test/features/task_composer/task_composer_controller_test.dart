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
      headers: {
        'content-type': 'application/json',
        ...response.headers,
      },
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
        } else if (request.url.path.endsWith('/tasks')) {
          return http.Response(jsonEncode({'tasks': []}), 200);
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
      controller.dispose();
    });

    test('cloud-only runtime keeps Ask Before Changes and refuses Autopilot/Offline', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/projects')) {
          return http.Response(
            jsonEncode({
              'projects': [
                {
                  'project_id': 'proj-1',
                  'display_name': 'Billing',
                  'root': 'C:/proj',
                  'local_autopilot_trusted': false,
                }
              ]
            }),
            200,
          );
        }
        if (request.url.path.endsWith('/models')) {
          return http.Response(
            jsonEncode({
              'models': [
                {
                  'name': 'gemma4:31b-cloud',
                  'provider': 'cloud',
                  'roles': ['builder'],
                  'available': true,
                  'supervised_testing_only': true,
                  'future_local_target': true,
                },
                {
                  'name': 'glm-5.2:cloud',
                  'provider': 'cloud',
                  'roles': ['chat', 'planner', 'builder'],
                  'available': true,
                  'supervised_testing_only': true,
                  'future_local_target': false,
                },
              ]
            }),
            200,
          );
        }
        if (request.url.path.endsWith('/tasks')) {
          return http.Response(jsonEncode({'tasks': []}), 200);
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskComposerController(client: engineClient);
      await controller.load();

      expect(controller.isCloudAssistedOnly, isTrue);
      expect(controller.hasLocalBuilder, isFalse);

      controller.selectMode('local_autopilot');
      expect(controller.selectedMode, equals('ask_before_changes'));
      expect(controller.isAutopilotBlockedByCloud, isFalse);

      controller.setOffline(true);
      expect(controller.offline, isFalse);

      controller.updateRequestText('Fix billing totals');
      expect(controller.isValid, isTrue);
      expect(controller.selectedMode, equals('ask_before_changes'));
      expect(controller.isCloudBuilderSelected, isTrue);

      controller.dispose();
    });

    test('submitTask() creates accepted task and DOES NOT automatically approve', () async {
      final requestedUrls = <String>[];
      final fakeClient = FakeHttpClient((request) async {
        requestedUrls.add(request.url.path);
        return http.Response(
          jsonEncode({
            'task_id': 'task-101',
            'status': 'accepted',
            'events': [
              {
                'sequence': 1,
                'kind': 'accepted',
                'detail': 'task persisted; draft a plan then prepare a proposal before writes',
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

      expect(requestedUrls, contains('/api/v1/tasks'));
      expect(requestedUrls.any((url) => url.contains('/approve')), isFalse);

      expect(status, isNotNull);
      expect(status!.taskId, equals('task-101'));
      expect(status.status, equals('accepted'));
      expect(controller.isAccepted, isTrue);
      expect(controller.isWaitingForApproval, isFalse);
      expect(status.events.first.kind, equals('accepted'));
      controller.dispose();
    });

    test('approveActiveTask() requires digest and reloads durable timeline', () async {
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
              'proposal': {
                'digest': 'abc123digest',
                'summary': 'Proposal for 1 file',
                'diffs': {'app.py': '+fixed'},
                'files': ['app.py'],
              },
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'task_id': 'task-101',
            'status': 'waiting_for_approval',
            'proposal': {
              'digest': 'abc123digest',
              'summary': 'Proposal for 1 file',
              'diffs': {'app.py': '+fixed'},
              'files': ['app.py'],
            },
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
      expect(controller.activeProposal?.digest, equals('abc123digest'));

      final approvedStatus = await controller.approveActiveTask();

      expect(approveRequest.method, equals('POST'));
      expect(approveRequest.url.path, equals('/api/v1/tasks/task-101/approve'));
      final body = jsonDecode((approveRequest as http.Request).body) as Map<String, dynamic>;
      expect(body['digest'], equals('abc123digest'));

      expect(approvedStatus, isNotNull);
      expect(approvedStatus!.status, equals('running'));
      expect(controller.isWaitingForApproval, isFalse);
      expect(approvedStatus.events.length, equals(2));
      expect(approvedStatus.events[1].kind, equals('approved'));
      controller.dispose();
    });

    test('cloud warning flag activates when waiting for approval with cloud builder model', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response(
          jsonEncode({
            'task_id': 'task-102',
            'status': 'waiting_for_approval',
            'proposal': {
              'digest': 'digest-cloud',
              'summary': 'cloud proposal',
              'diffs': {},
              'files': [],
            },
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
      controller.dispose();
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
      expect(controller.showProviderInputPanel, isFalse);
      expect(controller.isValid, isFalse);
      expect(await controller.sendProviderInput(), isNull);
      controller.updateProviderInputText('go ahead');
      final result = await controller.sendProviderInput();

      expect(sentMessage, 'go ahead');
      expect(result!.status, 'completed');
      expect(result.events.last.kind, 'completed');
      expect(controller.providerInputText, isEmpty);
      controller.dispose();
    });

    test('draftActivePlan surfaces engine hint and candidate chips on 422', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/plan-draft')) {
          return http.Response(
            jsonEncode({
              'ok': false,
              'reason': 'edit_plan_ambiguous:billing.py,invoicing.py',
              'hint': 'Multiple files match — tap a candidate chip or name one path explicitly.',
              'candidates': ['billing.py', 'invoicing.py'],
              'intent': {'kind': 'edit'},
            }),
            422,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response(
          jsonEncode({
            'task_id': 'task-plan',
            'status': 'accepted',
            'events': [],
          }),
          202,
          headers: {'content-type': 'application/json'},
        );
      });

      final controller = TaskComposerController(
        client: WiSenseEngineClient(client: fakeClient),
      );
      const model = EngineModelProfile(
        name: 'gemma4:31b-cloud',
        provider: 'cloud',
        roles: ['builder', 'chat'],
        available: true,
        supervisedTestingOnly: true,
        futureLocalTarget: true,
      );
      const project = EngineProject(
        projectId: 'proj-1',
        displayName: 'WiSense',
        root: 'C:/wisense',
        localAutopilotTrusted: false,
      );
      controller.selectProject(project);
      controller.selectChatModel(model);
      controller.selectBuilderModel(model);
      controller.updateRequestText('fix totals');

      final submitted = await controller.submitTask();
      expect(submitted, isNotNull);
      expect(controller.canDraftPlan, isTrue);

      final plan = await controller.draftActivePlan();
      expect(plan, isNull);
      expect(controller.planDraftHint, contains('candidate chip'));
      expect(controller.planDraftCandidates, equals(['billing.py', 'invoicing.py']));
      expect(controller.error, contains('edit_plan_ambiguous'));
      controller.dispose();
    });
  });
}
