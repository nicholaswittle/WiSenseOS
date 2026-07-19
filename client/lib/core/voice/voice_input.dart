import 'package:speech_to_text/speech_to_text.dart';

/// Platform speech recognition wrapped for Companion / Task Composer.
///
/// Transcription is ordinary text that feeds EngineClient submit — voice never
/// bypasses mode, approval, or budget gates.
abstract class VoiceInput {
  Future<bool> initialize();

  bool get isAvailable;

  bool get isListening;

  Future<void> start({
    required void Function(String words, bool isFinal) onResult,
    void Function(String message)? onError,
  });

  Future<void> stop();

  Future<void> cancel();
}

class SpeechToTextVoiceInput implements VoiceInput {
  SpeechToTextVoiceInput({SpeechToText? speech}) : _speech = speech ?? SpeechToText();

  final SpeechToText _speech;
  bool _available = false;
  bool _listening = false;

  @override
  bool get isAvailable => _available;

  @override
  bool get isListening => _listening;

  @override
  Future<bool> initialize() async {
    _available = await _speech.initialize(
      onError: (error) {
        _listening = false;
      },
      onStatus: (status) {
        if (status == 'done' || status == 'notListening') {
          _listening = false;
        }
      },
    );
    return _available;
  }

  @override
  Future<void> start({
    required void Function(String words, bool isFinal) onResult,
    void Function(String message)? onError,
  }) async {
    if (!_available) {
      onError?.call('Speech recognition is not available on this device.');
      return;
    }
    _listening = true;
    await _speech.listen(
      onResult: (result) {
        onResult(result.recognizedWords, result.finalResult);
      },
      listenOptions: SpeechListenOptions(
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 3),
        partialResults: true,
        cancelOnError: true,
        listenMode: ListenMode.dictation,
      ),
    );
  }

  @override
  Future<void> stop() async {
    await _speech.stop();
    _listening = false;
  }

  @override
  Future<void> cancel() async {
    await _speech.cancel();
    _listening = false;
  }
}
