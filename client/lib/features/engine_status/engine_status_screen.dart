import 'package:flutter/material.dart';

import '../../core/engine/engine_models.dart';
import 'engine_status_controller.dart';

class EngineStatusScreen extends StatefulWidget {
  const EngineStatusScreen({
    super.key,
    required this.controller,
  });

  final EngineStatusController controller;

  @override
  State<EngineStatusScreen> createState() => _EngineStatusScreenState();
}

class _EngineStatusScreenState extends State<EngineStatusScreen> {
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('WiSense OS'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: controller.loading ? null : controller.refresh,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _buildBody(context, controller),
    );
  }

  Widget _buildBody(BuildContext context, EngineStatusController controller) {
    if (controller.loading && controller.health == null) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (controller.error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.cloud_off, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(
                'Engine Offline',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                controller.error!,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.red.shade700,
                    ),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: controller.refresh,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry Connection'),
              ),
            ],
          ),
        ),
      );
    }

    final health = controller.health;
    final models = controller.models;

    return ListView(
      padding: const EdgeInsets.all(16.0),
      children: [
        if (health != null) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.check_circle, color: Colors.green),
                      const SizedBox(width: 8),
                      Text(
                        'Engine Active',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ],
                  ),
                  const Divider(height: 24),
                  Text('Engine: ${health.engine.isNotEmpty ? health.engine : "WiSense OS Engine"}'),
                  const SizedBox(height: 4),
                  Text('Status: ${health.status}'),
                  const SizedBox(height: 4),
                  Text('Version: ${health.version.isNotEmpty ? health.version : "v1.0.0"}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
        ],
        if (controller.diagnostics != null) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Onboard / Diagnostics',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const Divider(height: 24),
                  Text(
                    'Ollama: ${controller.diagnostics!.ollamaReachable ? "reachable" : "not reachable"}',
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Git: ${controller.diagnostics!.gitAvailable ? "available" : "missing"}',
                  ),
                  const SizedBox(height: 4),
                  Text(
                    controller.diagnostics!.cloudAssistedOnly
                        ? 'Mode: cloud-assisted — use Ask Before Changes'
                        : 'Mode: local builder available',
                  ),
                  if (controller.diagnostics!.notes.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    ...controller.diagnostics!.notes.map(
                      (note) => Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text('• $note', style: Theme.of(context).textTheme.bodySmall),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
        ],
        Text(
          'Model Profiles',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        if (models.isEmpty)
          const Text('No model profiles available.')
        else
          ...models.map((model) => _buildModelCard(context, model)),
      ],
    );
  }

  Widget _buildModelCard(BuildContext context, EngineModelProfile model) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12.0),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    model.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: model.available ? Colors.green.shade100 : Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    model.available ? 'Available' : 'Unavailable',
                    style: TextStyle(
                      color: model.available ? Colors.green.shade900 : Colors.grey.shade700,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text('Provider: ${model.provider}'),
            if (model.roles.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text('Roles: ${model.roles.join(', ')}'),
            ],
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                if (model.isCloud && model.supervisedTestingOnly)
                  const Chip(
                    avatar: Icon(Icons.cloud_outlined, size: 16),
                    label: Text('Cloud - supervised testing'),
                    backgroundColor: Color(0xFFE3F2FD),
                  ),
                if (!model.isCloud && model.supervisedTestingOnly)
                  const Chip(
                    label: Text('Supervised testing'),
                    backgroundColor: Color(0xFFE3F2FD),
                  ),
                if (model.futureLocalTarget)
                  const Chip(
                    avatar: Icon(Icons.hardware_outlined, size: 16),
                    label: Text('Future local target'),
                    backgroundColor: Color(0xFFFFF3E0),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
