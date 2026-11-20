import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/services.dart';

/// Sound + vibration after each scan.
/// In a warehouse the worker looks at the pack, not the screen, so they must HEAR / FEEL the result.
class ScanFeedback {
  final _player = AudioPlayer();

  /// short bright "beep-beep" + one light vibration
  void success() {
    _play('sounds/ok.wav'); // path is inside assets/
    HapticFeedback.mediumImpact();
  }

  /// low "buzz-buzz" + two strong vibrations, so an error is never missed
  Future<void> error() async {
    _play('sounds/error.wav');
    HapticFeedback.heavyImpact();
    await Future.delayed(const Duration(milliseconds: 200));
    HapticFeedback.heavyImpact();
  }

  Future<void> _play(String asset) async {
    try {
      await _player.stop(); // cut the previous sound if scans come fast
      await _player.play(AssetSource(asset));
    } catch (_) {
      // sound is a helper only: a muted phone or a blocked browser must never break scanning
    }
  }

  void dispose() => _player.dispose();
}
