import 'package:flutter/material.dart';

import 'core/engine/wisense_engine_client.dart';
import 'features/command_view/command_view_controller.dart';
import 'features/command_view/command_view_screen.dart';
import 'features/engine_status/engine_status_controller.dart';
import 'features/engine_status/engine_status_screen.dart';
import 'features/task_composer/task_composer_controller.dart';
import 'features/task_composer/task_composer_screen.dart';
import 'features/task_history/task_history_controller.dart';
import 'features/task_history/task_history_screen.dart';

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
  late final EngineStatusController _statusController;
  late final TaskComposerController _composerController;
  late final TaskHistoryController _historyController;
  late final CommandViewController _commandController;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _client = widget.client ?? WiSenseEngineClient();
    _statusController = EngineStatusController(client: _client);
    _composerController = TaskComposerController(client: _client);
    _historyController = TaskHistoryController(client: _client);
    _commandController = CommandViewController(client: _client);
  }

  @override
  void dispose() {
    _statusController.dispose();
    _composerController.dispose();
    _historyController.dispose();
    _commandController.dispose();
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
      home: Scaffold(
        body: IndexedStack(
          index: _currentIndex,
          children: [
            EngineStatusScreen(controller: _statusController),
            TaskComposerScreen(controller: _composerController),
            TaskHistoryScreen(controller: _historyController),
            CommandViewScreen(controller: _commandController),
          ],
        ),
        bottomNavigationBar: BottomNavigationBar(
          currentIndex: _currentIndex,
          type: BottomNavigationBarType.fixed,
          onTap: (index) {
            setState(() {
              _currentIndex = index;
            });
          },
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.dashboard_outlined),
              activeIcon: Icon(Icons.dashboard),
              label: 'Engine Status',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.edit_note_outlined),
              activeIcon: Icon(Icons.edit_note),
              label: 'Task Composer',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.history_outlined),
              activeIcon: Icon(Icons.history),
              label: 'Task History',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.analytics_outlined),
              activeIcon: Icon(Icons.analytics),
              label: 'Command View',
            ),
          ],
        ),
      ),
    );
  }
}
