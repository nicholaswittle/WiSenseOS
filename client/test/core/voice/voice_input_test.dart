import 'package:flutter_test/flutter_test.dart';
import 'package:wisense_os_client/core/voice/voice_input.dart';

class FakeVoiceInput implements VoiceInput {
  bool initialized = false;
  bool listening = false;
  String? lastError;
  void Function(String words, bool isFinal)? _onResult;

  @override
  bool get isAvailable => initialized;

  @override
  bool get isListening => listening;

  @override
  Future<bool> initialize() async {
    initialized = true;
    return true;
  }

  @override
  Future<void> start({
    required void Function(String words, bool isFinal) onResult,
    void Function(String message)? onError,
  }) async {
    listening = true;
    _onResult = onResult;
    lastError = null;
  }

  @override
  Future<void> stop() async {
    listening = false;
  }

  @override
  Future<void> cancel() async {
    listening = false;
  }

  void emit(String words, {bool isFinal = false}) {
    _onResult?.call(words, isFinal);
  }
}

void main() {
  test('FakeVoiceInput can simulate dictation for Companion wiring', () async {
    final voice = FakeVoiceInput();
    expect(await voice.initialize(), isTrue);
    final captured = <String>[];
    await voice.start(onResult: (words, isFinal) {
      captured.add('$words:$isFinal');
    });
    voice.emit('fix billing', isFinal: false);
    voice.emit('fix billing totals', isFinal: true);
    await voice.stop();
    expect(voice.isListening, isFalse);
    expect(captured, equals(['fix billing:false', 'fix billing totals:true']));
  });
}
