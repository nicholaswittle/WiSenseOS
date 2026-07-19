import 'package:flutter/material.dart';

import 'core/engine/wisense_engine_client.dart';
import 'features/engine_status/engine_status_controller.dart';
import 'features/engine_status/engine_status_screen.dart';

void main() {
  runApp(const WiSenseOSApp());
}

typedef MyApp = WiSenseOSApp;

class WiSenseOSApp extends StatefulWidget {

  const WiSenseOSApp({
    super.key,
    this.client,
  });

  final WiSenseEngineClient? client;

  @override
  State<WiSenseOSApp> createState() => _WiSenseOSAppState();
}

class _WiSenseOSAppState extends State<WiSenseOSApp> {
  late final WiSenseEngineClient _client;
  late final EngineStatusController _controller;

  @override
  void initState() {
    super.initState();
    _client = widget.client ?? WiSenseEngineClient();
    _controller = EngineStatusController(client: _client);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'WiSense OS',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: EngineStatusScreen(controller: _controller),
    );
  }
}
