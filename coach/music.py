"""Speech recognition over background music with lyrics, using the app's own code.

Each phrase is recorded "in a café": 1.5 s of music, the phrase, 1.5 s of music.
The music is a synthesized chord-and-beat track plus sung-style Korean and
English lyrics (data/noise/, made with edge-tts) as loud as the band.

For every phrase it checks:
- right answer: the phrase itself over music, should be accepted
- wrong answer: the next phrase of the same scenario over music, should be rejected
  (skipping phrases that contain an accepted form, e.g. "만 원 충전해 주세요" contains
  "충전해 주세요", which is accepted for "교통카드 충전해 주세요")

and compares the plain check with the app's fixes: finding the phrase inside the
transcript, and the scenario-phrase hint for Whisper (only as a careful second
try, see checker.check_spoken).

It also plays sounds with NO speech (a steady tone, fan-like noise, music without
a voice) for every target: nothing should be accepted. The first version of the
hint failed this: from a plain tone Whisper "heard" 아이스 아메리카노 한 잔 주세요.
Needs ffmpeg.

    uv run python evaluate_music.py
"""

import json
import subprocess
from pathlib import Path

import numpy as np

from coach import speech
from coach.checker import check, check_spoken, find_in_transcript, normalize

SR = 16000
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
rng = np.random.default_rng(1)


def decode(path):
    raw = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def rms(x):
    return np.sqrt(np.mean(x**2) + 1e-12)


def make_music(seconds=60):
    t = np.arange(SR * seconds) / SR
    chords = [(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)]
    band = np.zeros_like(t)
    for i in range(seconds // 2):  # a new chord every 2 s, with bass
        part = (t >= i * 2) & (t < i * 2 + 2)
        for f in chords[i % 4]:
            band[part] += 0.2 * (np.sin(2 * np.pi * f * t[part]) + 0.3 * np.sin(4 * np.pi * f * t[part]))
        band[part] += 0.3 * np.sin(np.pi * chords[i % 4][0] * t[part])
    for beat in np.arange(0, seconds, 0.5):  # kick and hi-hat
        n, k = int(beat * SR), np.arange(2000)
        band[n:n + 2000] += 0.8 * np.sin(2 * np.pi * 60 * k / SR) * np.exp(-k / 400)
        h = n + SR // 4
        band[h:h + 600] += 0.15 * rng.standard_normal(600) * np.exp(-np.arange(600) / 100)
    lines = [decode(p) for p in sorted((DATA_DIR / "noise").glob("l*.mp3"))]
    vocals, pos = np.zeros_like(t), 0
    while pos < len(t) - SR * 6:
        line = lines[rng.integers(len(lines))]
        vocals[pos:pos + len(line)] += line
        pos += len(line) + int(SR * 0.3)
    music = band / rms(band) + vocals / rms(vocals)
    return (music / rms(music)).astype(np.float32)


def in_cafe(clip, music, voice_db):
    """The phrase with music before, during and after; voice_db = how much louder the voice is."""
    pad = int(SR * 1.5)
    voice = np.concatenate([np.zeros(pad), clip, np.zeros(pad)]).astype(np.float32)
    start = rng.integers(0, len(music) - len(voice))
    background = music[start:start + len(voice)] * rms(clip) / (rms(music) * 10 ** (voice_db / 20))
    mixed = voice + background
    return (mixed / np.abs(mixed).max() * 0.9).astype(np.float32)


def main():
    scenarios = json.loads((DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))
    music = make_music()
    speech.load_model()
    methods = ["plain check", "+ find in transcript", "+ careful hint (app)"]
    print(f"{'':<26}" + "".join(f"{m:>24}" for m in methods))
    for voice_db in (10, 5, 0):
        right = dict.fromkeys(methods, 0)
        wrong = dict.fromkeys(methods, 0)
        total = 0
        for scenario in scenarios:
            chunks = scenario["chunks"]
            hint = " ".join(c["ko"] for c in chunks)
            for i, chunk in enumerate(chunks):
                accepted = [chunk["ko"], *chunk.get("alternatives", [])]
                others = chunks[i + 1:] + chunks[:i]
                other = next(o for o in others
                             if not any(normalize(a) in normalize(o["ko"]) for a in accepted))
                total += 1
                for said, tally in ((chunk, right), (other, wrong)):
                    audio = {"raw": in_cafe(decode(DATA_DIR / "audio" / f"{said['id']}.mp3"), music, voice_db),
                             "sampling_rate": SR}
                    heard = speech.transcribe(dict(audio))
                    tally["plain check"] += check(heard, accepted)[0] != "wrong"
                    tally["+ find in transcript"] += find_in_transcript(heard, accepted)[0] != "wrong"
                    retry = lambda: speech.transcribe(dict(audio), hint=hint)  # noqa: E731
                    tally["+ careful hint (app)"] += check_spoken(heard, accepted, (), retry)[0] != "wrong"
        label = f"voice {voice_db:>2} dB over music"
        print(f"{label + ' ✓ right':<26}" + "".join(f"{f'{right[m]}/{total} accepted':>24}" for m in methods))
        print(f"{'':<17}{'✗ wrong':<9}" + "".join(f"{f'{wrong[m]}/{total} accepted':>24}" for m in methods))
    no_speech(scenarios, music)


def no_speech(scenarios, music):
    """Sounds without any speech must never be accepted as an answer."""
    seconds = 3
    t = np.arange(SR * seconds) / SR
    sounds = {
        "tone": 0.3 * np.sin(2 * np.pi * 220 * t),
        "fan noise": 0.1 * rng.standard_normal(len(t)),
        "music only (a singer, no learner)": 0.3 * music[: len(t)] / np.abs(music[: len(t)]).max(),
    }
    print("\nNo speech at all (should never be accepted):")
    for label, sound in sounds.items():
        accepted_count = total = 0
        examples = set()
        audio = {"raw": sound.astype(np.float32), "sampling_rate": SR}
        plain = speech.transcribe(dict(audio))
        for scenario in scenarios:
            hint = " ".join(c["ko"] for c in scenario["chunks"])
            hinted = speech.transcribe(dict(audio), hint=hint)
            for chunk in scenario["chunks"]:
                accepted = [chunk["ko"], *chunk.get("alternatives", [])]
                total += 1
                if check_spoken(plain, accepted, (), lambda: hinted)[0] != "wrong":
                    accepted_count += 1
                    examples.add(chunk["ko"])
        print(f"  {label:<16} {accepted_count}/{total} accepted   (heard without hint: {plain!r})"
              + (f"  e.g. {sorted(examples)[:2]}" if examples else ""))


if __name__ == "__main__":
    main()
