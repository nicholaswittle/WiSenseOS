import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';
import 'package:wisense_os_client/features/task_history/task_history_controller.dart';

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
  group('TaskHistoryController', () {
    test('loadTasks() fetches task history and sets default selection', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/tasks')) {
          return http.Response(
            jsonEncode({
              'tasks': [
                {
                  'task_id': 'task-001',
                  'status': 'waiting_for_approval',
                  'events': [
                    {'sequence': 1, 'kind': 'proposal_ready', 'detail': 'Proposal ready'}
                  ],
                },
                {
                  'task_id': 'task-000',
                  'status': 'completed',
                  'events': [],
                }
              ]
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskHistoryController(client: engineClient);

      expect(controller.loading, isFalse);
      expect(controller.tasks, isEmpty);

      await controller.loadTasks();

      expect(controller.loading, isFalse);
      expect(controller.tasks.length, equals(2));
      expect(controller.selectedTask?.taskId, equals('task-001'));
      expect(controller.error, isNull);
    });

    test('draftPlan() calls draftTaskPlan endpoint and sets currentPlan', () async {
      late http.BaseRequest capturedRequest;
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.contains('/plan-draft')) {
          capturedRequest = request;
          return http.Response(
            jsonEncode({
              'ok': true,
              'task_id': 'task-001',
              'plan': {
                'title': 'Fix Billing Totals',
                'summary': 'Calculates correct tax sum',
                'files': ['lib/billing.py'],
                'api_contract': ['POST /api/v1/calculate'],
                'acceptance': ['pytest test_billing.py passes'],
                'source': 'heuristics',
              }
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'tasks': [
              {'task_id': 'task-001', 'status': 'waiting_for_approval'}
            ]
          }),
          200,
        );
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskHistoryController(client: engineClient);
      await controller.loadTasks();

      final plan = await controller.draftPlan('task-001');

      expect(capturedRequest.method, equals('POST'));
      expect(capturedRequest.url.path, equals('/api/v1/tasks/task-001/plan-draft'));

      expect(plan, isNotNull);
      expect(plan!.title, equals('Fix Billing Totals'));
      expect(plan.files, contains('lib/billing.py'));
      expect(controller.currentPlan, equals(plan));
    });

    test('cancelTask() calls cancelTask endpoint and reloads task history', () async {
      late http.BaseRequest cancelRequest;
      var listCallCount = 0;

      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/cancel')) {
          cancelRequest = request;
          return http.Response(
            jsonEncode({'task_id': 'task-001', 'status': 'cancelled'}),
            200,
          );
        } else if (request.url.path.endsWith('/tasks')) {
          listCallCount++;
          final status = listCallCount > 1 ? 'cancelled' : 'waiting_for_approval';
          return http.Response(
            jsonEncode({
              'tasks': [
                {'task_id': 'task-001', 'status': status}
              ]
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = TaskHistoryController(client: engineClient);
      await controller.loadTasks();

      expect(controller.selectedTask?.status, equals('waiting_for_approval'));

      final cancelledStatus = await controller.cancelTask('task-001');

      expect(cancelRequest.method, equals('POST'));
      expect(cancelRequest.url.path, equals('/api/v1/tasks/task-001/cancel'));

      expect(cancelledStatus, isNotNull);
      expect(cancelledStatus!.status, equals('cancelled'));
      expect(controller.selectedTask?.status, equals('cancelled'));
    });
  });
}
