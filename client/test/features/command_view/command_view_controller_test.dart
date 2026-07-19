import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';
import 'package:wisense_os_client/features/command_view/command_view_controller.dart';

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
  group('CommandViewController', () {
    test('refresh() loads telemetry, active tasks, and focused evidence', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/telemetry')) {
          return http.Response(
            jsonEncode({
              'compute': {
                'vram_used_mb': null,
                'vram_total_mb': null,
                'tokens_per_sec': null,
                'active_local_runs': 0,
                'active_cloud_runs': 1,
                'instrumented': false,
              },
              'qualification': [],
              'budget': {
                'cap_usd': 20.0,
                'confirmed_usd': 0.1,
                'reserved_usd': 0.0,
                'exposure_usd': 0.1,
              },
            }),
            200,
          );
        }
        if (request.url.path.endsWith('/tasks') && request.method == 'GET') {
          return http.Response(
            jsonEncode({
              'tasks': [
                {
                  'task_id': 'task-1',
                  'status': 'waiting_for_approval',
                  'reason': 'proposal ready',
                  'request': {
                    'request': 'Fix billing totals',
                    'mode': 'ask_before_changes',
                    'builder_model': 'gemma4:31b-cloud',
                    'chat_model': 'glm-5.2:cloud',
                    'project_root': 'C:/proj',
                  },
                }
              ]
            }),
            200,
          );
        }
        if (request.url.path.endsWith('/tasks/task-1')) {
          return http.Response(
            jsonEncode({
              'task_id': 'task-1',
              'status': 'waiting_for_approval',
              'reason': 'proposal ready',
              'request': {
                'request': 'Fix billing totals',
                'mode': 'ask_before_changes',
                'builder_model': 'gemma4:31b-cloud',
                'chat_model': 'glm-5.2:cloud',
                'project_root': 'C:/proj',
              },
              'events': [
                {'sequence': 1, 'kind': 'accepted', 'detail': 'persisted'},
                {'sequence': 2, 'kind': 'proposal_ready', 'detail': 'digest abc'},
              ],
              'proposal': {
                'digest': 'abc123',
                'summary': '1 file changed',
                'files': ['billing.py'],
                'diffs': {'billing.py': '- return 0\n+ return sum(items)\n'},
              },
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = CommandViewController(client: engineClient);

      await controller.refresh();

      expect(controller.error, isNull);
      expect(controller.telemetry!.compute.activeCloudRuns, equals(1));
      expect(controller.activeTasks.length, equals(1));
      expect(controller.focusedTask?.taskId, equals('task-1'));
      expect(controller.focusedTask?.proposal?.digest, equals('abc123'));
      expect(controller.focusedTask?.events.length, equals(2));
      expect(controller.focusedTask?.requestText, equals('Fix billing totals'));
    });

    test('refresh() sets error state when telemetry endpoint fails', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response('Server Error', 500);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = CommandViewController(client: engineClient);

      await controller.refresh();

      expect(controller.loading, isFalse);
      expect(controller.telemetry, isNull);
      expect(controller.error, isNotNull);
      expect(controller.error, contains('Failed to load command view'));
    });
  });
}
