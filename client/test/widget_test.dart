import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';
import 'package:wisense_os_client/main.dart';

class _FakeClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final body = request.url.path.endsWith('/health')
        ? {'engine': 'wisense-os', 'status': 'ready', 'version': '0.1.0'}
        : {
            'models': [
              {
                'name': 'gemma4:31b-cloud',
                'provider': 'cloud',
                'roles': ['builder'],
                'available': true,
                'supervised_testing_only': true,
                'future_local_target': true,
              }
            ]
          };
    return http.StreamedResponse(Stream.value(utf8.encode(jsonEncode(body))), 200);
  }
}

void main() {
  testWidgets('WiSense OS displays engine and truthful cloud profile', (tester) async {
    await tester.pumpWidget(WiSenseOSApp(
      client: WiSenseEngineClient(client: _FakeClient()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('WiSense OS'), findsOneWidget);
    expect(find.text('Engine Active'), findsOneWidget);
    expect(find.text('Cloud - supervised testing'), findsOneWidget);
    expect(find.text('Future local target'), findsOneWidget);
  });
}
