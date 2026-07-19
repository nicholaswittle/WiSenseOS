import 'package:flutter/material.dart';

import '../../core/engine/engine_models.dart';
import 'command_view_controller.dart';

class CommandViewScreen extends StatefulWidget {
  const CommandViewScreen({
    super.key,
    required this.controller,
    this.onSelectTask,
  });

  final CommandViewController controller;
  final ValueChanged<EngineTaskStatus>? onSelectTask;

  @override
  State<CommandViewScreen> createState() => _CommandViewScreenState();
}

class _CommandViewScreenState extends State<CommandViewScreen> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onControllerChanged);
    widget.controller.refresh();
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    super.dispose();
  }

  void _onControllerChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;

    if (controller.loading && controller.telemetry == null) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    final compute = controller.telemetry?.compute;
    final qualification = controller.telemetry?.qualification ?? const [];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Command'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: controller.loading ? null : controller.refresh,
            tooltip: 'Refresh Telemetry',
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

          // Live Compute & Hardware Card
          if (compute != null) ...[
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(
                side: BorderSide(color: Colors.deepPurple.shade200, width: 1.5),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.memory, color: Colors.deepPurple),
                        const SizedBox(width: 8),
                        Text(
                          'Hardware & Compute Telemetry',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: Colors.deepPurple.shade900,
                              ),
                        ),
                      ],
                    ),
                    const Divider(height: 24),

                    // VRAM Meter — null means not instrumented (never invent values)
                    Text(
                      compute.instrumented && compute.vramUsedMb != null && compute.vramTotalMb != null
                          ? 'VRAM Allocation: ${compute.vramUsedMb} MB / ${compute.vramTotalMb} MB'
                          : 'VRAM Allocation: not instrumented',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 6),
                    LinearProgressIndicator(
                      value: (compute.instrumented &&
                              compute.vramUsedMb != null &&
                              compute.vramTotalMb != null &&
                              compute.vramTotalMb! > 0)
                          ? (compute.vramUsedMb! / compute.vramTotalMb!).clamp(0.0, 1.0)
                          : 0.0,
                      backgroundColor: Colors.grey.shade200,
                      color: Colors.deepPurple,
                      minHeight: 10,
                    ),
                    const SizedBox(height: 16),

                    // Speed Meter & Run Counters Row
                    Row(
                      children: [
                        Expanded(
                          child: _buildMetricTile(
                            context,
                            icon: Icons.speed,
                            label: 'Generation Speed',
                            value: compute.tokensPerSec == null
                                ? 'n/a'
                                : '${compute.tokensPerSec!.toStringAsFixed(1)} tok/s',
                            color: Colors.teal,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _buildMetricTile(
                            context,
                            icon: Icons.computer,
                            label: 'Active Local Runs',
                            value: '${compute.activeLocalRuns}',
                            color: Colors.green,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _buildMetricTile(
                            context,
                            icon: Icons.cloud,
                            label: 'Active Cloud Runs',
                            value: '${compute.activeCloudRuns}',
                            color: Colors.blue,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
          ],

          Text(
            'Active Task Operations',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 6),
          Text(
            'Live timeline, proposal digests, and diffs for in-flight engine work.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          if (controller.activeTasks.isEmpty)
            const Card(
              child: ListTile(
                leading: Icon(Icons.inbox_outlined),
                title: Text('No active tasks'),
                subtitle: Text('Accepted, exploring, waiting, or running work will appear here.'),
              ),
            )
          else
            ...controller.activeTasks.map((task) {
              final selected = controller.focusedTask?.taskId == task.taskId;
              return Card(
                color: selected ? Colors.deepPurple.shade50 : null,
                child: ListTile(
                  leading: Icon(
                    selected ? Icons.play_circle_fill : Icons.play_circle_outline,
                    color: Colors.deepPurple,
                  ),
                  title: Text(
                    task.requestText.isEmpty ? task.taskId : task.requestText,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    '${task.status} · ${task.mode.isEmpty ? 'mode n/a' : task.mode}'
                    '${task.builderModel.isEmpty ? '' : ' · ${task.builderModel}'}',
                  ),
                  trailing: selected ? const Icon(Icons.check) : null,
                  onTap: () => controller.focusTask(task.taskId),
                ),
              );
            }),
          if (controller.focusedTask != null) ...[
            const SizedBox(height: 12),
            _buildFocusedTaskPanel(context, controller.focusedTask!),
          ],
          const SizedBox(height: 20),

          if (controller.telemetry?.budget != null) ...[
            Text(
              'Cloud Budget',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Card(
              child: ListTile(
                leading: const Icon(Icons.account_balance_wallet_outlined),
                title: Text(
                  'Exposure \$${controller.telemetry!.budget!.exposureUsd.toStringAsFixed(4)} / cap \$${controller.telemetry!.budget!.capUsd.toStringAsFixed(2)}',
                ),
                subtitle: Text(
                  'Confirmed \$${controller.telemetry!.budget!.confirmedUsd.toStringAsFixed(4)} · Reserved \$${controller.telemetry!.budget!.reservedUsd.toStringAsFixed(4)}',
                ),
              ),
            ),
            const SizedBox(height: 20),
          ],

          // Qualification Scorecard
          Text(
            'Model Qualification Scorecard',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 6),
          Text(
            'Offline corpus only. Cloud builders record as not_applicable — that is expected '
            'before a local builder is installed. Do not treat N/A as a failed qualification.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.tonalIcon(
              onPressed: controller.runningQualification
                  ? null
                  : controller.runOfflineQualification,
              icon: controller.runningQualification
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.science_outlined),
              label: Text(
                controller.runningQualification
                    ? 'Recording baselines…'
                    : 'Refresh qualification baselines',
              ),
            ),
          ),
          const SizedBox(height: 8),
          if (qualification.isEmpty)
            const Text('No model qualification benchmarks recorded.')
          else
            ...qualification.map((score) => _buildQualificationTile(context, score)),
        ],
      ),
    );
  }

  Widget _buildFocusedTaskPanel(BuildContext context, EngineTaskStatus task) {
    final proposal = task.proposal;
    final events = task.events;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Focused task evidence',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              task.taskId,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (task.reason != null && task.reason!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(task.reason!),
            ],
            if (task.status == 'waiting_for_approval' || task.status == 'waiting_for_provider_input') ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.amber.shade50,
                  border: Border.all(color: Colors.amber.shade400, width: 1.5),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.warning_amber_rounded, color: Colors.amber.shade900),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            task.status == 'waiting_for_approval'
                                ? 'Task Awaiting Approval!'
                                : 'Engine Clarification Needed!',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Colors.amber.shade900,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      task.status == 'waiting_for_approval'
                          ? 'Review proposal digest and approve handoff to execute changes.'
                          : 'Engine is waiting for your input to proceed.',
                      style: TextStyle(fontSize: 12, color: Colors.grey.shade800),
                    ),
                    const SizedBox(height: 10),
                    ElevatedButton.icon(
                      onPressed: () => widget.onSelectTask?.call(task),
                      icon: const Icon(Icons.open_in_new),
                      label: const Text('Open Task to Review & Approve'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.deepPurple,
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            ],
            if (proposal != null) ...[
              const SizedBox(height: 12),
              Text(
                'Proposal',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              Text(proposal.summary),
              Text(
                'Digest ${proposal.digest}',
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
              const SizedBox(height: 8),
              if (proposal.diffs.isEmpty)
                const Text('No textual diffs in this proposal.')
              else
                ...proposal.diffs.entries.map((entry) {
                  final preview = entry.value.length > 800
                      ? '${entry.value.substring(0, 800)}\n…'
                      : entry.value;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          entry.key,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(8),
                          color: Colors.grey.shade100,
                          child: Text(
                            preview.isEmpty ? '(no diff text)' : preview,
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 11,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }),
            ],
            const SizedBox(height: 12),
            Text(
              'Timeline',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            if (events.isEmpty)
              const Text('No durable events yet.')
            else
              ...events.map(
                (event) => ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Text('#${event.sequence}'),
                  title: Text(event.kind),
                  subtitle: Text(event.detail),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricTile(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String value,
    required MaterialColor color,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: color.shade800),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(fontSize: 11, color: color.shade900),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: color.shade900,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQualificationTile(
    BuildContext context,
    EngineQualificationScore score,
  ) {
    final isNa = score.status == 'not_applicable';
    final isFailed = score.status == 'failed';
    final badgeColor = isFailed
        ? Colors.red
        : (isNa ? Colors.blueGrey : Colors.green);
    final scoreLabel = score.score == null
        ? 'No numeric score (${score.status})'
        : 'Qualification Score: ${score.score!.toStringAsFixed(1)}';

    return Card(
      margin: const EdgeInsets.only(bottom: 8.0),
      child: ListTile(
        leading: Icon(
          isNa ? Icons.cloud_off_outlined : Icons.fact_check_outlined,
          color: badgeColor,
        ),
        title: Text(
          score.name,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Text(
          score.detail.isEmpty ? scoreLabel : '$scoreLabel\n${score.detail}',
        ),
        isThreeLine: score.detail.isNotEmpty,
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: badgeColor.shade100,
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            score.status.toUpperCase(),
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: badgeColor.shade900,
            ),
          ),
        ),
      ),
    );
  }
}
