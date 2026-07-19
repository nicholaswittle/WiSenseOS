import 'package:flutter/foundation.dart';

import '../../core/engine/engine_models.dart';
import '../../core/engine/wisense_engine_client.dart';

class SOPLibraryController extends ChangeNotifier {
  SOPLibraryController({required this.client});

  final WiSenseEngineClient client;

  bool _loading = false;
  String? _error;
  List<EngineSOPWorkflow> _sops = const [];

  bool get loading => _loading;
  String? get error => _error;
  List<EngineSOPWorkflow> get sops => _sops;

  Future<void> loadSOPs() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      _sops = await client.listSOPs();
      _loading = false;
      notifyListeners();
    } catch (e) {
      _loading = false;
      _error = 'Failed to load SOP workflows: $e';
      notifyListeners();
    }
  }
}
