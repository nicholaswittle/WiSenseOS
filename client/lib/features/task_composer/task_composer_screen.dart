import 'package:flutter/material.dart';

import '../../core/engine/engine_models.dart';
import 'task_composer_controller.dart';

class TaskComposerScreen extends StatefulWidget {
  const TaskComposerScreen({
    super.key,
    required this.controller,
  });

  final TaskComposerController controller;

  @override
  State<TaskComposerScreen> createState() => _TaskComposerScreenState();
}

class _TaskComposerScreenState extends State<TaskComposerScreen> {
  final TextEditingController _textController = TextEditingController();

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onControllerChanged);
    widget.controller.load();
    _textController.text = widget.controller.requestText;
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _textController.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    if (mounted) {
      if (_textController.text != widget.controller.requestText) {
        _textController.text = widget.controller.requestText;
      }
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;

    if (controller.loading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Task Composer'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: controller.submitting ? null : controller.load,
            tooltip: 'Reload Projects & Models',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          if (controller.error != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                border: Border.all(color: Colors.red.shade200),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                controller.error!,
                style: TextStyle(color: Colors.red.shade900),
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Project Dropdown
          Text(
            'Active Project',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          DropdownButtonFormField<EngineProject>(
            initialValue: controller.selectedProject,
            isExpanded: true,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 14),
            ),
            hint: const Text('Select a registered project'),
            items: controller.projects.map((project) {
              return DropdownMenuItem<EngineProject>(
                value: project,
                child: Text('${project.displayName} (${project.root})'),
              );
            }).toList(),
            onChanged: controller.submitting ? null : controller.selectProject,
          ),
          const SizedBox(height: 16),

          // Request Text Box
          Text(
            'Task Request',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _textController,
            maxLines: 4,
            enabled: !controller.submitting,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'e.g. Fix the totals bug in the billing module and run tests',
            ),
            onChanged: controller.updateRequestText,
          ),
          const SizedBox(height: 16),

          // Operating Mode Selector
          Text(
            'Operating Mode',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(
                value: 'talk_only',
                label: Text('Talk Only'),
                icon: Icon(Icons.chat_bubble_outline),
              ),
              ButtonSegment(
                value: 'ask_before_changes',
                label: Text('Ask Before Changes'),
                icon: Icon(Icons.rule),
              ),
              ButtonSegment(
                value: 'local_autopilot',
                label: Text('Local Autopilot'),
                icon: Icon(Icons.bolt),
              ),
            ],
            selected: {controller.selectedMode},
            onSelectionChanged: controller.submitting
                ? null
                : (newSelection) {
                    controller.selectMode(newSelection.first);
                  },
          ),
          if (controller.isAutopilotBlockedByCloud) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.amber.shade50,
                border: Border.all(color: Colors.amber.shade400),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.warning_amber_rounded, color: Colors.amber),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      controller.autopilotBlockedReason!,
                      style: TextStyle(color: Colors.amber.shade900),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 16),

          // Model Selection Row
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Chat/Planner Model',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<EngineModelProfile>(
                      initialValue: controller.selectedChatModel,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                      ),
                      items: controller.chatModels.map((model) {
                        return DropdownMenuItem<EngineModelProfile>(
                          value: model,
                          child: Text(_formatModelName(model)),
                        );
                      }).toList(),
                      onChanged: controller.submitting ? null : controller.selectChatModel,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Builder/Coder Model',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 6),
                    DropdownButtonFormField<EngineModelProfile>(
                      initialValue: controller.selectedBuilderModel,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                      ),
                      items: controller.builderModels.map((model) {
                        return DropdownMenuItem<EngineModelProfile>(
                          value: model,
                          child: Text(_formatModelName(model)),
                        );
                      }).toList(),
                      onChanged: controller.submitting ? null : controller.selectBuilderModel,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Submit Button
          SizedBox(
            height: 48,
            child: ElevatedButton.icon(
              onPressed: controller.isValid && !controller.submitting
                  ? () => controller.submitTask()
                  : null,
              icon: controller.submitting
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send),
              label: Text(
                controller.submitting ? 'Submitting Task...' : 'Submit Task to Engine',
              ),
            ),
          ),

          // Result Display Section
          if (controller.lastSubmissionResult != null) ...[
            const SizedBox(height: 24),
            _buildResultCard(context, controller.lastSubmissionResult!),
          ],
        ],
      ),
    );
  }

  String _formatModelName(EngineModelProfile model) {
    if (model.isCloud && model.supervisedTestingOnly) {
      return '${model.name} (Cloud - supervised testing)';
    } else if (model.futureLocalTarget) {
      return '${model.name} (Future local target)';
    }
    return model.name;
  }

  Widget _buildResultCard(BuildContext context, EngineTaskStatus result) {
    final isBlocked = result.isBlocked;
    final color = isBlocked ? Colors.orange : Colors.green;
    final icon = isBlocked ? Icons.block : Icons.check_circle_outline;

    return Card(
      color: isBlocked ? Colors.orange.shade50 : Colors.green.shade50,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: color, width: 1.5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color),
                const SizedBox(width: 8),
                Text(
                  isBlocked ? 'Task Blocked (${result.statusCode})' : 'Task Accepted (${result.statusCode})',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: color.shade900,
                        fontWeight: FontWeight.bold,
                      ),
                ),
              ],
            ),
            const Divider(height: 20),
            Text('Task ID: ${result.taskId.isNotEmpty ? result.taskId : "N/A"}'),
            Text('Status Stage: ${result.status}'),
            if (result.reason != null) ...[
              const SizedBox(height: 6),
              Text(
                'Reason: ${result.reason}',
                style: TextStyle(color: color.shade900, fontWeight: FontWeight.w600),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
