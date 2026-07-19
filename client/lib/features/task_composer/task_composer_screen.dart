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
  final TextEditingController _providerInputController = TextEditingController();

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
    _providerInputController.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    if (mounted) {
      if (_textController.text != widget.controller.requestText) {
        _textController.text = widget.controller.requestText;
      }
      if (_providerInputController.text != widget.controller.providerInputText) {
        _providerInputController.text = widget.controller.providerInputText;
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
            onPressed: controller.submitting || controller.approving
                ? null
                : controller.load,
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

          // Result Display Section & Task Timeline
          if (controller.activeTaskStatus != null) ...[
            const SizedBox(height: 24),
            _buildTaskPanel(context, controller, controller.activeTaskStatus!),
          ],
        ],
      ),
    );
  }

  String _formatModelName(EngineModelProfile model) {
    if (model.supervisedTestingOnly) {
      return '${model.name} (Cloud — supervised testing)';
    } else if (model.futureLocalTarget) {
      return '${model.name} (Future local target)';
    }
    return model.name;
  }

  Widget _buildTaskPanel(
    BuildContext context,
    TaskComposerController controller,
    EngineTaskStatus result,
  ) {
    final isBlocked = result.isBlocked;
    final isWaiting = controller.isWaitingForApproval;
    final isProviderInput = controller.isWaitingForProviderInput;
    final plan = controller.activePlan;
    final color = isBlocked
        ? Colors.orange
        : (isWaiting || isProviderInput ? Colors.blue : Colors.green);

    return Card(
      color: isBlocked
          ? Colors.orange.shade50
          : (isWaiting || isProviderInput ? Colors.blue.shade50 : Colors.green.shade50),
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
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(
                      isBlocked
                          ? Icons.block
                          : (isWaiting ? Icons.hourglass_top : Icons.check_circle_outline),
                      color: color,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      isBlocked
                          ? 'Task Blocked (${result.statusCode})'
                          : 'Task Status (${result.statusCode})',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: color.shade900,
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                  ],
                ),
                OutlinedButton.icon(
                  onPressed: controller.approving ? null : controller.refreshTaskStatus,
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Refresh Task Status'),
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
            if (isWaiting || isProviderInput) ...[
              const SizedBox(height: 8),
              TextButton.icon(
                onPressed: controller.canceling ? null : controller.cancelActiveTask,
                icon: const Icon(Icons.cancel_outlined),
                label: Text(controller.canceling ? 'Canceling Task...' : 'Cancel Task'),
              ),
            ],

            if (isWaiting) ...[
              const SizedBox(height: 16),
              if (plan == null)
                OutlinedButton.icon(
                  onPressed: controller.draftingPlan ? null : controller.draftActivePlan,
                  icon: controller.draftingPlan
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.fact_check_outlined),
                  label: Text(controller.draftingPlan ? 'Drafting Evidence Plan...' : 'Draft Evidence Plan Before Handoff'),
                )
              else
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.indigo.shade50,
                    border: Border.all(color: Colors.indigo.shade200),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(plan.title, style: TextStyle(fontWeight: FontWeight.bold, color: Colors.indigo.shade900)),
                      const SizedBox(height: 4),
                      Text(plan.summary),
                      const SizedBox(height: 8),
                      const Text('Evidence-backed files:', style: TextStyle(fontWeight: FontWeight.bold)),
                      ...plan.files.map((file) => Text(file)),
                      const SizedBox(height: 8),
                      const Text('Acceptance:', style: TextStyle(fontWeight: FontWeight.bold)),
                      ...plan.acceptance.map((item) => Text('- $item')),
                    ],
                  ),
                ),
            ],

            // Approval Handoff Section
            if (isWaiting) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade100,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.verified_user, color: Colors.blue),
                        const SizedBox(width: 8),
                        Text(
                          'Explicit Approval Required',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.blue.shade900,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Approval is required before the Engine contacts a model or modifies project files.',
                      style: TextStyle(color: Colors.blue.shade900),
                    ),
                    if (controller.showCloudApprovalWarning) ...[
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.amber.shade100,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: Colors.amber.shade600),
                        ),
                        child: Text(
                          'Cloud Profile Warning: Approving this task will execute requests using the cloud builder profile "${controller.selectedBuilderModel?.name}" (supervised testing).',
                          style: TextStyle(
                            color: Colors.amber.shade900,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: controller.approving
                            ? null
                            : controller.approveActiveTask,
                        icon: controller.approving
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.check_circle),
                        label: Text(
                          controller.approving
                              ? 'Approving Engine Handoff...'
                              : 'Approve Engine Handoff',
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.blue.shade700,
                          foregroundColor: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            if (isProviderInput) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade100,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Work Center Response Required',
                      style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue.shade900),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'The Work Center needs your explicit response before it can continue. Nothing is sent automatically.',
                      style: TextStyle(color: Colors.blue.shade900),
                    ),
                    if (controller.isCloudBuilderSelected) ...[
                      const SizedBox(height: 8),
                      Text(
                        'Cloud Profile Warning: a response such as "go ahead" may permit the selected cloud builder to spend quota.',
                        style: TextStyle(color: Colors.amber.shade900, fontWeight: FontWeight.bold),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextField(
                      controller: _providerInputController,
                      enabled: !controller.sendingProviderInput,
                      decoration: const InputDecoration(
                        border: OutlineInputBorder(),
                        labelText: 'Your response to Work Center',
                        hintText: 'For example: go ahead',
                      ),
                      onChanged: controller.updateProviderInputText,
                    ),
                    const SizedBox(height: 8),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: controller.sendingProviderInput || controller.providerInputText.trim().isEmpty
                            ? null
                            : controller.sendProviderInput,
                        icon: controller.sendingProviderInput
                            ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.send),
                        label: Text(controller.sendingProviderInput ? 'Sending Explicit Response...' : 'Send Response to Work Center'),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            // Task Events Timeline
            const SizedBox(height: 16),
            Text(
              'Task Event Timeline',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            if (result.events.isEmpty)
              const Text('No events recorded yet.')
            else
              ...result.events.map((event) => _buildEventTile(context, event)),
          ],
        ),
      ),
    );
  }

  Widget _buildEventTile(BuildContext context, EngineTaskEvent event) {
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 12,
            backgroundColor: Colors.deepPurple.shade100,
            child: Text(
              '${event.sequence}',
              style: TextStyle(fontSize: 10, color: Colors.deepPurple.shade900),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.grey.shade200,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        event.kind,
                        style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(event.detail, style: const TextStyle(fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
