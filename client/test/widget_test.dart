import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:wisense_os_client/core/engine/wisense_engine_client.dart';
import 'package:wisense_os_client/main.dart';

class _FakeClient extends http.BaseClient {
  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    Map<String, dynamic> body;
    final path = request.url.path;
    if (path.contains('/health')) {
      body = {'engine': 'wisense-os', 'status': 'ready', 'version': '0.1.0'};
    } else if (path.contains('/models')) {
      body = {
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
    } else if (path.contains('/projects')) {
      body = {'projects': []};
    } else if (path.contains('/tasks')) {
      body = {'tasks': []};
    } else if (path.contains('/telemetry')) {
      body = {
        'compute': {
          'vram_used_mb': 100,
          'vram_total_mb': 1000,
          'tokens_per_sec': 10.0,
          'active_local_runs': 0,
          'active_cloud_runs': 0,
        },
        'qualification': [],
      };
    } else if (path.contains('/diagnostics')) {
      body = {
        'ollama_reachable': true,
        'git_available': true,
        'cloud_assisted_only': true,
        'models_runtime': ['gemma4:31b-cloud'],
        'notes': [],
        'engine': {'version': '1.0.0'},
      };
    } else if (path.contains('/sops')) {
      body = {'sops': []};
    } else {
      body = {};
    }
    return http.StreamedResponse(
      Stream.value(utf8.encode(jsonEncode(body))),
      200,
      headers: {'content-type': 'application/json'},
    );
  }
}

void main() {
  testWidgets('WiSense OS displays engine and truthful cloud profile', (tester) async {
    await tester.pumpWidget(WiSenseOSApp(
      client: WiSenseEngineClient(
        client: _FakeClient(),
        tokenProvider: () async => 'test-token',
      ),
    ));

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('WiSense OS'), findsOneWidget);
    expect(find.text('Engine Active'), findsOneWidget);
    expect(find.textContaining('Cloud'), findsWidgets);
    expect(find.text('Future local target'), findsOneWidget);
  });
}
