import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';
import 'package:wisense_os_client/features/sop_library/sop_library_controller.dart';

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
  group('SOPLibraryController', () {
    test('loadSOPs() successfully fetches builtin agentic workflows', () async {
      final fakeClient = FakeHttpClient((request) async {
        if (request.url.path.endsWith('/sops')) {
          return http.Response(
            jsonEncode({
              'sops': [
                {
                  'id': 'code_audit',
                  'name': 'Security & Quality Audit',
                  'category': 'Audit',
                  'description': 'Comprehensive security check',
                  'default_request': 'Perform security audit',
                  'recommended_mode': 'ask_before_changes',
                }
              ]
            }),
            200,
          );
        }
        return http.Response('Not Found', 404);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = SOPLibraryController(client: engineClient);

      expect(controller.loading, isFalse);
      expect(controller.sops, isEmpty);

      await controller.loadSOPs();

      expect(controller.loading, isFalse);
      expect(controller.error, isNull);
      expect(controller.sops.length, equals(1));
      expect(controller.sops[0].id, equals('code_audit'));
      expect(controller.sops[0].name, equals('Security & Quality Audit'));
    });

    test('loadSOPs() sets error state on HTTP failure', () async {
      final fakeClient = FakeHttpClient((request) async {
        return http.Response('Server Error', 500);
      });

      final engineClient = WiSenseEngineClient(client: fakeClient);
      final controller = SOPLibraryController(client: engineClient);

      await controller.loadSOPs();

      expect(controller.loading, isFalse);
      expect(controller.sops, isEmpty);
      expect(controller.error, isNotNull);
      expect(controller.error, contains('Failed to load SOP workflows'));
    });
  });
}
