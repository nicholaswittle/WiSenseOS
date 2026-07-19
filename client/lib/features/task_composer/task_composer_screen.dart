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
  final TextEditingController _resolveController = TextEditingController();
  bool _isListening = false;

  void _toggleVoiceInput() {
    setState(() {
      _isListening = !_isListening;
      if (_isListening && _textController.text.isEmpty) {
        _textController.text = 'Fix the totals bug in the billing module and run relevant tests';
        widget.controller.updateRequestText(_textController.text);
      }
    });
  }

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
    _resolveController.dispose();
    super.dispose();
  }

  Future<void> _showRegisterProjectDialog() async {
    final nameController = TextEditingController();
    final rootController = TextEditingController();
    var trusted = false;
    final registered = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Register Project'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      labelText: 'Display name',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: rootController,
                    decoration: const InputDecoration(
                      labelText: 'Root path',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Trust for Local Autopilot'),
                    value: trusted,
                    onChanged: (value) => setDialogState(() => trusted = value ?? false),
                  ),
                ],
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Register'),
                ),
              ],
            );
          },
        );
      },
    );
    if (registered == true) {
      await widget.controller.registerProject(
        displayName: nameController.text.trim(),
        root: rootController.text.trim(),
        localAutopilotTrusted: trusted,
      );
    }
    nameController.dispose();
    rootController.dispose();
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

  Future<void> _approveEngineHandoff(TaskComposerController controller) async {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Approval button clicked — contacting the local Engine…')),
    );
    await controller.approveActiveTask();
    // The approval endpoint starts work asynchronously. Refreshing after the
    // request makes the visible state move even if the worker has not yet
    // emitted its next event when the 202 response arrives.
    await controller.refreshTaskStatus();
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

          // Project Dropdown + nickname resolve + register
          Row(
            children: [
              Expanded(
                child: Text(
                  'Active Project',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              TextButton.icon(
                onPressed: controller.registering ? null : _showRegisterProjectDialog,
                icon: controller.registering
                    ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.create_new_folder_outlined, size: 18),
                label: const Text('Register'),
              ),
            ],
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
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _resolveController,
                  enabled: !controller.resolving,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    hintText: 'Resolve nickname, e.g. the billing project',
                    contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                  ),
                  onChanged: controller.updateResolvePhrase,
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: controller.resolving ? null : controller.resolveNickname,
                child: Text(controller.resolving ? '…' : 'Resolve'),
              ),
            ],
          ),
          if (controller.resolveMessage != null) ...[
            const SizedBox(height: 6),
            Text(
              controller.resolveMessage!,
              style: TextStyle(color: Colors.blueGrey.shade800, fontStyle: FontStyle.italic),
            ),
          ],
          const SizedBox(height: 16),

          // Request Text Box
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Task Request',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              IconButton(
                icon: Icon(_isListening ? Icons.mic : Icons.mic_none),
                color: _isListening ? Colors.red : Colors.deepPurple,
                tooltip: _isListening ? 'Stop Voice Dictation' : 'Start Voice Dictation',
                onPressed: _toggleVoiceInput,
              ),
            ],
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _textController,
            maxLines: 4,
            enabled: !controller.submitting,
            decoration: InputDecoration(
              border: const OutlineInputBorder(),
              hintText: 'e.g. Fix the totals bug in the billing module and run tests',
              suffixIcon: _isListening
                  ? const Padding(
                      padding: EdgeInsets.all(8.0),
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.red),
                    )
                  : null,
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
            segments: [
              const ButtonSegment(
                value: 'talk_only',
                label: Text('Talk Only'),
                icon: Icon(Icons.chat_bubble_outline),
              ),
              const ButtonSegment(
                value: 'ask_before_changes',
                label: Text('Ask Before Changes'),
                icon: Icon(Icons.rule),
              ),
              ButtonSegment(
                value: 'local_autopilot',
                label: const Text('Local Autopilot'),
                icon: const Icon(Icons.bolt),
                enabled: controller.hasLocalBuilder,
              ),
            ],
            selected: {controller.selectedMode},
            onSelectionChanged: controller.submitting
                ? null
                : (newSelection) {
                    controller.selectMode(newSelection.first);
                  },
          ),
          if (controller.isCloudAssistedOnly) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blueGrey.shade50,
                border: Border.all(color: Colors.blueGrey.shade300),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.cloud_outlined, color: Colors.blueGrey.shade700),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Cloud-assisted operation: no offline builder is installed yet. '
                      'Use Ask Before Changes; Local Autopilot and Offline unlock after the hardware upgrade.',
                      style: TextStyle(color: Colors.blueGrey.shade900),
                    ),
                  ),
                ],
              ),
            ),
          ],
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
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Offline (local models only)'),
            subtitle: Text(
              controller.isCloudAssistedOnly
                  ? 'Unavailable until a local builder is installed — cloud routes would all be blocked.'
                  : 'Hard-blocks every cloud route, including planning and recovery.',
            ),
            value: controller.offline,
            onChanged: (controller.submitting || controller.isCloudAssistedOnly)
                ? null
                : controller.setOffline,
          ),
          if (controller.offlineBlockedReason != null) ...[
            const SizedBox(height: 4),
            Text(
              controller.offlineBlockedReason!,
              style: TextStyle(color: Colors.red.shade800, fontSize: 12),
            ),
          ],
          const SizedBox(height: 8),

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
    final isAccepted = controller.isAccepted;
    final isProviderInput = controller.isWaitingForProviderInput;
    final plan = controller.activePlan;
    final proposal = controller.activeProposal;
    final color = isBlocked
        ? Colors.orange
        : (isWaiting || isProviderInput || isAccepted ? Colors.blue : Colors.green);

    return Card(
      color: isBlocked
          ? Colors.orange.shade50
          : (isWaiting || isProviderInput || isAccepted ? Colors.blue.shade50 : Colors.green.shade50),
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
                          : (isWaiting || isAccepted ? Icons.hourglass_top : Icons.check_circle_outline),
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
            if (controller.lastAction != null) ...[
              const SizedBox(height: 6),
              Text(
                controller.lastAction!,
                style: TextStyle(color: Colors.blueGrey.shade800, fontStyle: FontStyle.italic),
              ),
            ],
            if (result.reason != null) ...[
              const SizedBox(height: 6),
              Text(
                'Reason: ${result.reason}',
                style: TextStyle(color: color.shade900, fontWeight: FontWeight.w600),
              ),
            ],
            if (controller.canCancelActiveTask) ...[
              const SizedBox(height: 8),
              TextButton.icon(
                onPressed: controller.canceling ? null : controller.cancelActiveTask,
                icon: const Icon(Icons.cancel_outlined),
                label: Text(controller.canceling ? 'Canceling Task...' : 'Cancel Task'),
              ),
            ],

            if (isAccepted || isWaiting) ...[
              const SizedBox(height: 16),
              if (plan == null)
                OutlinedButton.icon(
                  onPressed: controller.canDraftPlan ? controller.draftActivePlan : null,
                  icon: controller.draftingPlan
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.fact_check_outlined),
                  label: Text(controller.draftingPlan ? 'Drafting Evidence Plan...' : 'Draft Evidence Plan'),
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
                      if (controller.canPrepareProposal) ...[
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: controller.proposing ? null : controller.prepareProposal,
                            icon: controller.proposing
                                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                                : const Icon(Icons.difference_outlined),
                            label: Text(
                              controller.proposing
                                  ? 'Preparing Proposal…'
                                  : 'Prepare Proposal (model may run; no writes yet)',
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
            ],

            if (proposal != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.teal.shade50,
                  border: Border.all(color: Colors.teal.shade200),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Write Proposal',
                      style: TextStyle(fontWeight: FontWeight.bold, color: Colors.teal.shade900),
                    ),
                    const SizedBox(height: 4),
                    Text(proposal.summary),
                    const SizedBox(height: 4),
                    SelectableText(
                      'Digest: ${proposal.digest}',
                      style: TextStyle(fontFamily: 'monospace', fontSize: 12, color: Colors.teal.shade900),
                    ),
                    const SizedBox(height: 8),
                    const Text('Diffs:', style: TextStyle(fontWeight: FontWeight.bold)),
                    ...proposal.diffs.entries.map(
                      (entry) => Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(entry.key, style: const TextStyle(fontWeight: FontWeight.w600)),
                            const SizedBox(height: 4),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(8),
                              color: Colors.black87,
                              child: SelectableText(
                                entry.value.isEmpty ? '(no textual diff)' : entry.value,
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 11,
                                  color: Colors.greenAccent,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            // Approval Handoff Section — digest-bound write gate
            if (isWaiting && proposal != null) ...[
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
                          'Digest-Bound Write Approval',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: Colors.blue.shade900,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Approval applies the exact proposal digest above. Project files are unchanged until you approve.',
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
                          'Cloud Profile Warning: Approving will apply a proposal prepared with cloud builder "${controller.selectedBuilderModel?.name}" (supervised testing).',
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
                            : () => _approveEngineHandoff(controller),
                        icon: controller.approving
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.check_circle),
                        label: Text(
                          controller.approving
                              ? 'Approving Write…'
                              : 'Approve & Apply Proposal',
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
