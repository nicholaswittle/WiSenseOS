import 'package:flutter/material.dart';

import '../../core/engine/engine_models.dart';
import 'sop_library_controller.dart';

class SOPLibraryScreen extends StatefulWidget {
  const SOPLibraryScreen({
    super.key,
    required this.controller,
    this.onSelectSOP,
  });

  final SOPLibraryController controller;
  final ValueChanged<EngineSOPWorkflow>? onSelectSOP;

  @override
  State<SOPLibraryScreen> createState() => _SOPLibraryScreenState();
}

class _SOPLibraryScreenState extends State<SOPLibraryScreen> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onControllerChanged);
    widget.controller.loadSOPs();
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

    if (controller.loading && controller.sops.isEmpty) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('SOP & Workflow Library'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: controller.loading ? null : controller.loadSOPs,
            tooltip: 'Refresh SOPs',
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
          Text(
            'Pre-Packaged Agentic Workflows',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 4),
          Text(
            'Execute automated Standard Operating Procedures directly against your active projects.',
            style: TextStyle(color: Colors.grey.shade700),
          ),
          const SizedBox(height: 16),
          if (controller.sops.isEmpty)
            const Text('No SOP workflows available.')
          else
            ...controller.sops.map((sop) => _buildSOPCard(context, sop)),
        ],
      ),
    );
  }

  Widget _buildSOPCard(BuildContext context, EngineSOPWorkflow sop) {
    IconData icon;
    Color color;

    switch (sop.category.toLowerCase()) {
      case 'audit':
        icon = Icons.security;
        color = Colors.red;
        break;
      case 'testing':
        icon = Icons.checklist;
        color = Colors.green;
        break;
      case 'refactoring':
        icon = Icons.build_circle;
        color = Colors.deepPurple;
        break;
      case 'documentation':
        icon = Icons.description;
        color = Colors.blue;
        break;
      default:
        icon = Icons.auto_awesome;
        color = Colors.teal;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12.0),
      elevation: 2,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: Colors.grey.shade300),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color, size: 24),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    sop.name,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: color.withAlpha(30),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    sop.category.toUpperCase(),
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              sop.description,
              style: TextStyle(color: Colors.grey.shade800),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey.shade100,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                'Task Prompt: "${sop.defaultRequest}"',
                style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => widget.onSelectSOP?.call(sop),
                icon: const Icon(Icons.play_arrow),
                label: const Text('Execute SOP Workflow'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.deepPurple,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
