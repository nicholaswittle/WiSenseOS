import 'package:flutter/material.dart';

import '../../core/engine/engine_models.dart';
import 'command_view_controller.dart';

class CommandViewScreen extends StatefulWidget {
  const CommandViewScreen({
    super.key,
    required this.controller,
  });

  final CommandViewController controller;

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
        title: const Text('Command View & Telemetry'),
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
