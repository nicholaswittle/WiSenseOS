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
    test('refresh() loads honest telemetry without inventing qualification', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/telemetry')) {
          return http.Response(
            jsonEncode({
              'compute': {
                'vram_used_mb': null,
                'vram_total_mb': null,
                'tokens_per_sec': null,
                'active_local_runs': 1,
                'active_cloud_runs': 0,
                'instrumented': false,
              },
              'qualification': [],
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = CommandViewController(client: engineClient);

      expect(controller.loading, isFalse);
      expect(controller.telemetry, isNull);

      await controller.refresh();

      expect(controller.loading, isFalse);
      expect(controller.error, isNull);
      expect(controller.telemetry, isNotNull);
      expect(controller.telemetry!.compute.vramUsedMb, isNull);
      expect(controller.telemetry!.compute.vramTotalMb, isNull);
      expect(controller.telemetry!.compute.tokensPerSec, isNull);
      expect(controller.telemetry!.compute.activeLocalRuns, equals(1));
      expect(controller.telemetry!.compute.instrumented, isFalse);
      expect(controller.telemetry!.qualification, isEmpty);
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
      expect(controller.error, contains('Failed to load telemetry'));
    });
  });
}
