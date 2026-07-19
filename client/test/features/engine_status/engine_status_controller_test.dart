import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';
import 'package:wisense_os_client/features/engine_status/engine_status_controller.dart';

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
  group('EngineStatusController', () {
    test('refresh() successfully loads health and models', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/health')) {
          return http.Response(
            jsonEncode({
              'engine': 'WiSense Engine',
              'status': 'ok',
              'version': '1.0.0',
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
                  'roles': ['builder'],
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
                },
                {
                  'name': 'gemma4:31b',
                  'provider': 'ollama',
                  'roles': ['builder'],
                  'available': false,
                  'supervised_testing_only': false,
                  'future_local_target': true,
                },
              ]
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = EngineStatusController(client: engineClient);

      expect(controller.loading, isFalse);
      expect(controller.health, isNull);
      expect(controller.models, isEmpty);
      expect(controller.error, isNull);

      await controller.refresh();

      expect(controller.loading, isFalse);
      expect(controller.error, isNull);
      expect(controller.health, isNotNull);
      expect(controller.health!.status, equals('ok'));
      expect(controller.health!.version, equals('1.0.0'));
      expect(controller.models.length, equals(3));

      // Prove cloud labeling data
      final cloudModel = controller.models.firstWhere((m) => m.name == 'claude-3-7-sonnet');
      expect(cloudModel.supervisedTestingOnly, isTrue);
      expect(cloudModel.futureLocalTarget, isFalse);

      // Prove future local target labeling data
      final futureLocalModel = controller.models.firstWhere((m) => m.name == 'gemma4:31b');
      expect(futureLocalModel.futureLocalTarget, isTrue);
      expect(futureLocalModel.supervisedTestingOnly, isFalse);
    });

    test('refresh() sets error state when engine is offline or returns error', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response('Internal Error', 500);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = EngineStatusController(client: engineClient);

      await controller.refresh();

      expect(controller.loading, isFalse);
      expect(controller.health, isNull);
      expect(controller.models, isEmpty);
      expect(controller.error, isNotNull);
      expect(controller.error, contains('Engine is offline or unreachable'));
    });
  });
}
