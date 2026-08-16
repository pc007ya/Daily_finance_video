from __future__ import annotations

import os
from pathlib import Path
import azure.cognitiveservices.speech as speechsdk

VOICE = "zh-TW-HsiaoChenNeural"


def synthesize_ssml(ssml: str, output_path: str | Path) -> Path:
    key = os.environ["AZURE_SPEECH_KEY"]
    region = os.environ["AZURE_SPEECH_REGION"]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = VOICE
    audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output))
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = getattr(result, "cancellation_details", None)
        raise RuntimeError(f"Azure TTS failed: {details}")

    return output
