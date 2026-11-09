"""Speech recognition: turn a spoken Korean answer into text.

Three models can be chosen (the app's sidebar and its 🔬 Model lab page), compared on
the app's own tests in compare_asr.py:

- Whisper small (OpenAI, default): fast, solid in noise.
- Whisper large-v3-turbo (OpenAI): most accurate with loud music, but slow on a CPU.
- Qwen3-ASR 0.6B (Alibaba): fastest, doesn't invent words from silence, weaker in noise.
  It needs an older `transformers`, so it runs as a helper process in its own
  environment (qwen/worker.py, qwen/requirements.txt).

All run on this computer, so recordings never leave it. The text then goes through the
same checks as a typed answer.

Speech recognition writes what a fluent speaker *meant*, so it often fixes small
pronunciation mistakes. It tells you whether the right phrase came out
understandably, not how good the pronunciation was.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

APP_DIR = Path(__file__).resolve().parents[1]
SR = 16000

# What the app shows when someone picks a model. Numbers come from compare_asr.py:
# 2 CPU cores (like the free Hugging Face Space), music test = voice as loud as the music.
ENGINES = {
    "whisper-small": {
        "label": "Whisper small", "tag": "Fast · default", "model": "openai/whisper-small",
        "speed": "about 2 seconds per answer",
        "pros": ["Quick enough for every answer", "Good in noise: 22 / 28 phrases with loud music"],
        "cons": ["Can invent words from silence (the app filters these out)"],
    },
    "whisper-turbo": {
        "label": "Whisper large-v3-turbo", "tag": "Slow · most accurate", "model": "openai/whisper-large-v3-turbo",
        "speed": "about 1 minute per answer on the free server (no GPU)",
        "pros": ["Most accurate with loud music: 26 / 28 phrases"],
        "cons": ["Very slow without a graphics card: you'll wait about a minute per answer",
                 "Can invent words from silence (the app filters these out)"],
    },
    "qwen3-asr": {
        "label": "Qwen3-ASR", "tag": "Fastest", "model": "Qwen/Qwen3-ASR-0.6B",
        "speed": "under 1 second per answer (first use loads for ~1 minute)",
        "pros": ["Fastest: about 3× quicker than Whisper small", "Doesn't invent words from silence"],
        "cons": ["Less accurate when it's noisy: 20 / 28 phrases with loud music"],
    },
}
DEFAULT_ENGINE = "whisper-small"
MODEL_NAME = ENGINES[DEFAULT_ENGINE]["model"]

# Whisper invents sentences from silence (often "시청해주셔서 감사합니다"),
# so recordings quieter than this are treated as "nothing heard".
SILENCE_LEVEL = 0.003
# Beam search keeps 3 candidate transcriptions instead of 1. In our noise test
# (phrases mixed with café chatter or static), 3 beams got 64/112 right, as
# good as Whisper's default 5 (63) and better than greedy decoding (55).
# The token cap stops runaway repetition, which Whisper sometimes falls
# into on unclear audio.
GENERATE = {"language": "korean", "task": "transcribe", "num_beams": 3, "max_new_tokens": 64}


def qwen_python():
    """The Python of Qwen's own environment (QWEN_PYTHON, or .venv-qwen in this folder)."""
    return os.environ.get("QWEN_PYTHON") or str(APP_DIR / ".venv-qwen" / "bin" / "python")


def on_streamlit_cloud():
    """Streamlit Community Cloud runs apps from /mount/src."""
    return Path("/mount/src").is_dir()


def allowed_engines():
    """Models this copy of the app may use. SPEECH_MODELS="whisper-small,qwen3-asr" picks them;
    on Streamlit Community Cloud (about 1-2.7 GB of memory) only Whisper small fits."""
    names = os.environ.get("SPEECH_MODELS")
    if names:
        return [name.strip() for name in names.split(",")]
    return [DEFAULT_ENGINE] if on_streamlit_cloud() else list(ENGINES)


def is_available(engine=DEFAULT_ENGINE):
    if engine not in allowed_engines():
        return False
    if engine == "qwen3-asr":
        return Path(qwen_python()).exists()
    try:
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def available_engines():
    return [name for name in ENGINES if is_available(name)]


@lru_cache(maxsize=2)
def load_model(engine=DEFAULT_ENGINE):
    """Load a model once (Whisper: a transformers pipeline; Qwen: start the helper process)."""
    if engine == "qwen3-asr":
        return _QwenWorker()
    from transformers import pipeline

    return pipeline("automatic-speech-recognition", model=ENGINES[engine]["model"])


class _QwenWorker:
    """Talks to qwen/worker.py: one JSON line per request and per reply."""

    def __init__(self):
        log = open(Path(tempfile.gettempdir()) / "qwen-worker.log", "a")  # noqa: SIM115
        self.process = subprocess.Popen(
            [qwen_python(), str(APP_DIR / "qwen" / "worker.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True, encoding="utf-8",
        )
        self.lock = threading.Lock()  # one answer at a time, even with several users
        self.next_id = 0
        ready = self.process.stdout.readline()
        if not ready or not json.loads(ready).get("ready"):
            raise RuntimeError("Qwen3-ASR helper didn't start; see qwen-worker.log in the temp folder")

    def transcribe(self, audio, context=""):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            path = handle.name
        try:
            write_wav(path, audio)
            with self.lock:
                self.next_id += 1
                self.process.stdin.write(json.dumps({"id": self.next_id, "path": path, "context": context}) + "\n")
                self.process.stdin.flush()
                reply = json.loads(self.process.stdout.readline())
        finally:
            os.unlink(path)
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply["text"]


def write_wav(path, audio):
    samples = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(samples.tobytes())


def wav_to_array(wav_bytes):
    """Read 16-bit WAV bytes (what st.audio_input records) into floats from -1 to 1."""
    with wave.open(io.BytesIO(wav_bytes)) as wav:
        rate, channels = wav.getframerate(), wav.getnchannels()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    audio = samples.astype(np.float32) / 32768
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate


# Noisy surroundings: how loud the background is, and how far the voice stands out from it.
# Calibrated on the app's phrases mixed with the café music from coach/music.py: a quiet room
# measures about -55 dBFS with the voice 35-40 dB above it; music 10 dB below the voice gives a
# 17-18 dB margin, 5 dB below 12-13 dB, and as loud as the voice 8-9 dB. Whisper still passes
# 27/28 phrases at 5 dB below but only 22/28 at "as loud", so "noisy" is a heads-up that starts
# early (under 20 dB; a real room with café noise measured -40 dBFS / 16 dB and recognition still
# worked) and "very noisy" (under 10 dB) means it will probably mishear. A soft voice in a quiet
# room (-55 dBFS) is never flagged.
NOISE_FLOOR_DB = -45
NOISY_MARGIN_DB = 20
VERY_NOISY_MARGIN_DB = 10


def noise_measure(audio):
    """(background dBFS, voice margin dB, level) of a recording; level is "quiet", "noisy" or
    "very noisy". Splits it into 30 ms frames: the quietest (15th percentile) are the
    background, the loudest (95th) the voice."""
    x = to_array(audio)
    frame = SR * 30 // 1000
    count = len(x) // frame
    if count < 10:
        return None, None, "quiet"
    frames = x[: count * frame].reshape(count, frame)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    background, voice = float(np.percentile(db, 15)), float(np.percentile(db, 95))
    margin = voice - background
    if background < NOISE_FLOOR_DB:
        level = "quiet"
    elif margin < VERY_NOISY_MARGIN_DB:
        level = "very noisy"
    else:
        level = "noisy" if margin < NOISY_MARGIN_DB else "quiet"
    return background, margin, level


def surroundings(audio):
    """How noisy a recording's surroundings are: "quiet", "noisy" or "very noisy"."""
    return noise_measure(audio)[2]


def to_array(audio):
    """Any recording (WAV/webm/mp3 bytes, a file path, or {"raw", "sampling_rate"}) → 16 kHz floats."""
    if isinstance(audio, dict):
        raw = np.asarray(audio["raw"], dtype=np.float32)
        if audio["sampling_rate"] == SR:
            return raw
        source = {"input": raw.tobytes(),
                  "args": ["-f", "f32le", "-ac", "1", "-ar", str(audio["sampling_rate"]), "-i", "pipe:0"]}
    elif isinstance(audio, bytes):
        try:
            array, rate = wav_to_array(audio)
            if rate == SR:
                return array
        except wave.Error:
            pass
        source = {"input": audio, "args": ["-i", "pipe:0"]}
    else:
        source = {"input": None, "args": ["-i", str(audio)]}
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", *source["args"], "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        input=source["input"], capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def transcribe(audio, hint="", engine=DEFAULT_ENGINE):
    """Korean text from a recording (see to_array). Returns "" when the recording is silent.

    hint: words the speaker is likely to use (the lesson's phrases). Whisper reads it as
    "previous text" and Qwen as "context"; it steers recognition toward those words and
    away from background lyrics. The app only uses it as a careful second try
    (checker.check_spoken), because with no real speech a model can "hear" a hint phrase.
    """
    array = to_array(audio)
    if array.size == 0 or np.sqrt(np.mean(array**2)) < SILENCE_LEVEL:
        return ""
    model = load_model(engine)
    if engine == "qwen3-asr":
        return model.transcribe(array, hint)
    options = dict(GENERATE)
    if hint:
        options["prompt_ids"] = model.tokenizer.get_prompt_ids(hint, return_tensors="pt").to(model.device)
    text = model({"raw": array, "sampling_rate": SR}, generate_kwargs=options)["text"].strip()
    if hint and text.startswith(hint.strip()):  # some versions echo the hint back
        text = text[len(hint.strip()):].strip()
    return text


if __name__ == "__main__":  # quick check: python speech.py <audio file> [engine]
    print(transcribe(sys.argv[1], engine=sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ENGINE))
