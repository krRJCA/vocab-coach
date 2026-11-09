# How it works

The design, research basis, evaluation and developer notes behind Scenario Vocab Coach.
For using the app, see the [README](../README.md); for how it was built step by step, see
[PROCESS.md](PROCESS.md); for putting it online, see [DEPLOY.md](DEPLOY.md).

## Why Busan needs this (goal)

Busan is actively recruiting international students (over 24,000 by early 2025),
and its Korean support for them is mostly **in person**:

| Who | What they offer | Gap |
| --- | --- | --- |
| Busan Global City Foundation (BGCF) | Free Korean classes for foreign residents; since 2025 the **부산한글학당** hub Korean center for international students (TOPIK classes, 1:1 conversation, job-related Korean) | Classroom-based, fixed times, no self-study app found |
| 부산 외국인 유학생 통합지원 허브 ([mybusan.kr](https://mybusan.kr)) | One-stop help: registration, visa, banking, hospitals, Korean classes | Points to the classes above |
| Busan Office of Education | AI Korean learning program and interpretation | Only for K-12 multicultural students, not university students |
| King Sejong Institute (national) | Apps with AI conversation and speaking assessment | General Korean, not Busan's real situations (Busan Metro, local cafés, part-time job interviews) |

We found no Busan-specific app that trains international students for the situations
they meet in their first weeks in Busan. **Goal:** a self-study companion to
BGCF / 부산한글학당 classes. Students practice the city's real situations between
classes with spaced repetition and speaking practice, and teachers could add their
own scenarios as JSON.

(Based on a web search in November 2026; worth confirming with BGCF directly.)

## Why this design (research basis)

| Research finding | What the app does |
| --- | --- |
| **Retrieval practice / testing effect** (Roediger & Karpicke, 2006): recalling an answer builds memory far better than rereading it. | You see the English meaning and must *type the Korean* before the answer is shown. No passive flashcard flipping. |
| **Spaced repetition** (Ebbinghaus; Cepeda et al., 2006): reviews spread out over growing gaps beat cramming. | Leitner boxes: each phrase comes back after 1, 2, 4, 7, then 15 days. A wrong answer sends it back to box 1. |
| **Lexical chunks** (Lewis, *The Lexical Approach*; Boers & Lindstromberg): fluent speakers store and retrieve multi-word phrases, not single words. | The unit of learning is a chunk: *카드 돼요?*, *주말에도 일할 수 있습니다*. Grammar is explained inside the chunk. |
| **Task-based language teaching** (Ellis; Long): language sticks when it is used to complete a meaningful task. | Each scenario ends in a role-play with a *new* situation (hot latte instead of iced, Gwangalli instead of Haeundae), so the phrases have to transfer. |
| **Context and depth of processing** (Craik & Lockhart; Nation): words learned in meaningful context are remembered better. | Every chunk first appears in a model dialogue, with a usage note, the speech level, and a common mistake. |
| **High-frequency first** (Nation, 2001): a small set of common language covers most everyday situations. | Scenarios are the situations international students meet first: food, transport, work. |
| **Interleaving** (Rohrer & Taylor, 2007): mixing topics in practice improves transfer. | The daily review shuffles due phrases from all scenarios together. |

## Levels and scenarios

Lessons are grouped into levels, each ending in a **🏁 checkpoint** (`data/levels.json`).

| Level | Scenarios | Status |
| --- | --- | --- |
| **1 · First weeks in Busan** (부산 첫 달), Beginner, TOPIK 1 level | ☕ café · 🚇 getting around · 🍜 restaurant (돼지국밥) · 🏪 convenience store · 🐟 Jagalchi market · 💊 pharmacy · 🤝 making friends · 🏠 dorm life | 8 / 8 built (72 phrases) + **Checkpoint 1** |
| **2 · Settling in** (부산 생활 적응), Intermediate, TOPIK 2 level | 🏫 campus office · 💼 part-time job interview · 🏦 bank account · 📱 phone plan · 🏥 doctor · 🏘️ renting a one-room · 👥 group project · 🔁 refund / exchange | 2 / 8 built, 6 "coming soon"; Checkpoint 2 planned |

**Levels follow TOPIK** (한국어능력시험), the test international students need for admission,
visas and graduation: Level 1 aims at TOPIK 1 and Level 2 at TOPIK 2 (roughly CEFR A1 and A2).
The app trains speaking in real situations; it is not a TOPIK exam-prep tool, and the level
match is approximate.

**Why 8 Beginner scenarios before Intermediate:** Beginner ("survival") learning
is organised around the first everyday transactions: food, transport, shopping, health,
people and home. 8 scenarios × 9 phrases ≈ 72 phrases cover each of those areas once
(food twice: café and restaurant; shopping twice: convenience store and market). Korea's
official integration program (KIIP) spends about 100 class hours on each beginner stage,
so this app is a self-study companion to classes, not the whole course.

**Checkpoint 1: "Your first Saturday in Busan"** (부산에서의 첫 토요일)
- *Mixed test:* 16 phrases, 2 from each Level 1 lesson, interleaved, with no hints and no
  feedback until the end. **Pass at 80%** (13/16) to complete the level. A failed attempt
  lists the lessons to review.
- *Story role-play:* 8 turns in a row from different lessons (plan the day with a friend →
  ask the way to Jagalchi → buy fish → eat → pharmacy at night), in Practice or ⏱️ Time attack.
- *Open anytime:* it doubles as a placement test, so a stronger student can pass on day one.
- *Soft lock:* Level 2 lessons show "🔒 Recommended after Checkpoint 1" with a "Start
  anyway" button. Nothing is blocked, so teachers and advanced learners can open any lesson.

Adding a scenario is an entry in `data/scenarios.json`, its id in `data/levels.json`, and
`uv run python dev/make_audio.py`. All content was drafted with AI help and still needs a
native speaker's check.

## How a lesson works

1. **Situation** – a model dialogue played as one connected conversation: the line
   being spoken lights up, you can click any line to jump there, 🔁 repeats one line,
   and it can be slowed to 0.9× or 0.75×. Romanization and English can be hidden.
2. **Notice** – phrase cards: audio, meaning, speech level, usage note, common mistake.
3. **Recall** – type or **say** each phrase in Korean from the English meaning, then
   listen to the model and repeat. A hint shows the romanization, but then the
   phrase counts as not yet known.
4. **Role-play** – a new conversation in the same situation; the other person speaks,
   and you reply (typed or spoken) to complete a task. **Listening practice** hides
   their words until you ask.

   **Two modes:** *🗣️ Practice* (take your time, type or record) and *⏱️ Time attack*:
   their line plays, the recorder starts by itself, and you have a few seconds to
   answer, like a real conversation. The time limit is 1.5 s to react plus the
   shortest good answer at learner pace (about 2.5 syllables per second; native
   speakers talk at roughly twice that), between 3 and 10 s: 괜찮아요 gets 3 s,
   경험은 없지만 빨리 배우겠습니다 gets 7 s. Recording stops when you go quiet after
   speaking, and each reply shows how fast you started (≤ 2 s counts as natural pace).

Then **Review** (daily, mixed scenarios) and **Progress** (boxes, accuracy).

## Voice

- **Voice lines** (`dev/make_audio.py`): every dialogue line, phrase, and role-play
  prompt has a recording, made with **Supertonic 3**, an open-source TTS model by the
  Korean company Supertone that runs on the computer (no account; about 9 s per line on
  a laptop CPU). Each role keeps one of its built-in voices (staff F1, you M1, passer-by
  M2, station staff M3, owner M4, taxi driver M5), and phrase cards are read a little
  slower for learners. The MP3s are saved in `data/audio/`, so the app works offline.
- **Why Supertonic:** we started with Microsoft's neural voices (edge-tts), but they
  sounded a bit robotic and read some questions like statements. In a pilot on the café
  dialogue, Supertonic passed the same automatic checks, Whisper heard 5 of 6 questions
  as questions (writing "?") against 3 of 6 before, and after listening we switched. Options
  that need an account (Gemini TTS, ElevenLabs) were ruled out. Supertonic's model
  weights have their own license from Supertone; check it before publishing the app.
- **Caught by the automatic checks after the switch:** Supertonic read the digit in
  "5번 출구" wrongly (Whisper heard "밥원 출구") and said 앉으세요 like "안 주세요". Now the
  voice gets digits written in Hangul (5번 → 오 번) and a small pronunciation list
  (앉으세요 → 안즈세요); learners still see the normal spelling. After the fix all 118
  recordings pass, and the speech test still passes 28 / 28.
- **With 10 scenarios (428 recordings), the checks found 13 warnings:**
  - *Real voice problems:* 식후 was heard as "19" however it was spelled, so the line now
    says 식사 후 (the phrase card explains the short form 식후 on medicine labels).
    새 룸메이트 sounded like "셀럽메이트", now read as "새 룸 메이트". Room numbers were read
    "삼백이 호" and heard as "300이 호"; the number now stays joined to 호 (삼백이호). A line with
    a phone number read digit by digit (일이삼사) was rewritten.
  - *Checker problems:* the voices were right, but Whisper writes "1kg", "11시", "15,000원" and
    "1 플러스 1" where the lessons say 1킬로, 열한 시, 만 오천 원 and 원 플러스 원. A learner
    saying those phrases would have been marked wrong too. The checker now reads native
    numbers up to 열두/스무, joins split amounts (만 오천 = 15,000), and knows kg and 1+1.
  - After the fixes: all 428 recordings pass, and the speech test passes 91 / 91.
- **Clipped endings (found by a listener):** 학생증 있으세요? stopped mid-syllable. The trimming
  that makes conversations flow cut everything quieter than -45 dB at the end of a line, and a
  soft final 요 (especially a rising 요?) fades out below that; 100 ms before the file ended
  the voice was still at -24 dB. Now only true silence (-60 dB) is trimmed and 0.25 s is kept;
  all 203 dialogue and role-play lines were regenerated and now end at -63 dB or quieter.
  Conversation tracks subtract each line's quiet ending from the turn gap, so the pace stays
  the same. Two regenerated lines were misheard (뭐 찾아요 → "못 찾아요", 뭐예요 → "뭐해") and
  got pronunciation fixes. Result: all 428 recordings pass the automatic checks again.
- **Sounding like a conversation:** generated one by one, the lines first sounded
  disconnected: each clip had ~0.3 s of silence before it and ~1 s after, pauses of
  up to 1 s between sentences, and everything was 5% slow. Now dialogue lines are
  spoken at normal speed, ffmpeg trims the edges and shortens pauses inside a line to
  0.3 s (lines got 35-50% shorter), and each scenario's dialogue is joined into one
  track with 0.35 s between speakers, close to real turn-taking gaps. A timing file
  lets the player highlight each line.
- **Voice-line review:** every recording passes two steps before it counts as done.
  1. *Automatic checks* (`dev/evaluate_voices.py`): Whisper must understand the line, with
     no pause over 0.8 s, no clipping, and no extra silence at the edges of dialogue
     lines. All 118 recordings (82 lines + question versions) pass.
  2. *A person listens* on the app's **🎧 Voice check** page, approves each line or
     marks it for fixing with a note (`data/voice_review.json`), and for yes/no
     questions picks the most natural of three versions: the original voice, a gentle
     rise (+2.5 semitones on the last syllable, with Praat), or the text read with "??".
     The app switches to the chosen version right away.
     This page is **dev-only** (`dev/voice_check.py`, marked ᵈᵉᵛ in the tabs): it appears only
     when you run the app on your own computer and is never pushed or deployed.

  Why a person: the TTS voices sometimes read yes/no questions like statements
  (주문하시겠어요? sounded flat). We first forced a +5 semitone rise on every yes/no
  question and checked it with a pitch meter: the meter said it worked, but a listener
  found every question exaggerated. Pitch trackers also disagreed with each other on
  the same file (-2.3 vs +2.6 semitones), so intonation is judged by ear, not by numbers.
- **Speaking** (`coach/speech.py`): choose *🎙️ Speak* in the sidebar. The browser records
  your answer, and OpenAI's **Whisper** model
  ([`openai/whisper-small`](https://huggingface.co/openai/whisper-small)) turns it into
  Korean text on your computer. The text then goes through the same checks as a
  typed answer.
- **Noisy places:** in a café with music, Whisper usually *does* hear you, but it also
  writes down the song: "오늘 밤 우리 함께 춤을 춰 큰 사이즈로 주세요 사랑해…". So spoken
  answers are searched for the phrase *inside* the transcript (the fact rules still
  check the words around it, so a "안" just before it still counts), and Whisper gets
  the scenario's phrases as a hint. See "Background music" below.
- **Limit:** Whisper writes what a fluent speaker *meant*, so it often fixes small
  pronunciation mistakes. Speaking checks that the right phrase came out
  understandably; it does not grade pronunciation. Very quiet recordings are
  ignored, because Whisper tends to invent sentences from silence.

## Answer checking

Every answer goes through three steps:

1. **Spelling** (`coach/checker.py`): Hangul is split into jamo (주 → ㅈ + ㅜ) and
   compared with `difflib`, ignoring spaces and punctuation. `카드 되요?` for
   `카드 돼요?` is **close**: accepted, with the correct spelling shown.
2. **AI meaning** (`coach/semantic.py`): if the spelling is too different, a pretrained
   Korean sentence-embedding model from Hugging Face,
   [`jhgan/ko-sroberta-multitask`](https://huggingface.co/jhgan/ko-sroberta-multitask),
   compares meanings. Similarity ≥ 0.80 means **same meaning**: `카드 되나요?` (0.95)
   is accepted for `카드 돼요?`, but `카드로 계산할게요` ("I'll pay by card", a statement,
   0.68) is not.
3. **Fact rules** (`coach/checker.py`): embeddings miss small but important details, so
   both close and same-meaning answers must keep the same numbers (만 원 ≠ 이만 원),
   the same negation (돼요 ≠ 안 돼요), and the task's key words (따뜻한 라떼 ≠ 아이스 라떼).

Feedback always lists the other accepted answers too ("✅ Also correct: …"), so learners see
more than one natural way to say it.

In **role-play**, a same-meaning answer counts as understood: the goal is
communication. In **recall**, it is shown as "right meaning" but the phrase comes
back tomorrow: the goal is to learn that exact chunk.

The AI check can be switched off in the sidebar to compare.

## Where AI fits

- **AI-powered product:** two pretrained models (Method 2): Whisper for speech
  recognition and a Korean sentence-embedding model for the meaning check.
- **Generative AI:** neural text-to-speech voices for every line; dialogues and
  phrases drafted with generative AI, then checked and edited by hand (our own contribution).
- **Combined tools (Method 5):** speech → text → spelling check + AI meaning + fact rules.

## Evaluation

### Answer checking (`dev/evaluate.py`)

Realistic learner answers for the role-play turns, each labelled acceptable or not
(`data/eval_answers.json`). First 75 answers for the first three scenarios:

| Method | Accuracy | Good answers accepted | Wrong answers accepted |
| --- | --- | --- | --- |
| Spelling only (v1, no fact rules) | 53% | 18 / 47 | 6 / 28 |
| Spelling + fact rules | 61% | 18 / 47 | 0 / 28 |
| Spelling + fact rules + AI meaning | **96%** | **44 / 47** | **0 / 28** |

As scenarios were added, so were labelled answers (many of them tempting wrong ones: the
wrong document, language, body part, time, room number or payment method). Now **175
answers** for 10 scenarios and the checkpoint story: spelling + fact rules + AI meaning
**98%** (103 / 106 good accepted, **0 / 69** wrong accepted). Each round found real problems:

- A natural answer missing from the accepted list (재학증명서 떼러 왔어요).
- The number rule read 다시 **한**번 ("once again") as the number 1.
- Speech recognition writes numbers as digits (2명, 4,500원) while the lessons spell them
  out (두 명, 사천오백 원), so correct spoken answers failed. Numbers are now compared by
  value: 2명 = 두 명, 6천 원 = 육천 원, but 7천 원 ≠ 육천 원.
- The AI accepted "택배 **보내러** 왔어요" (to *send* a parcel) for picking one up (0.96
  similar), and "몇 시**까지**" (until) for "몇 시**부터**" (from). Fixed with task key words,
  the same fix as 아이스 vs 따뜻한 라떼: the embedding model misses small words that
  flip the meaning.

What we learned while building it:

- The multilingual model we tried first (`paraphrase-multilingual-MiniLM-L12-v2`)
  rated `먹고 갈게요` (for here) and `가져갈게요` (to go) as 0.995 similar, which is unusable.
  The Korean-specific model separated meanings much better.
- Even the good model scores `아이스 라떼` vs `따뜻한 라떼` at 0.87, so AI alone is
  not enough. The simple fact rules fixed every wrongly accepted answer.

```bash
uv run python dev/evaluate.py
```

### Speech recognition (`dev/evaluate_speech.py`)

Each phrase's voice line is sent through Whisper and the answer checker:

| Audio | Phrases passed | Time per answer |
| --- | --- | --- |
| Generated voices (`data/audio/`, 10 scenarios) | 91 / 91 (100%) | ~1 s |
| Real learner recordings (`data/recordings/`) | *to do* | |

In noise (`dev/evaluate_noise.py`): each phrase mixed with café chatter or static.
"5 dB" means the voice is a little louder than the noise; "0 dB" means equally loud.

| Noise | Greedy (1 guess) | Beam search, 3 | Beam search, 5 (Whisper default) |
| --- | --- | --- | --- |
| Café chatter, 5 dB | 17 / 28 | 19 / 28 | 20 / 28 |
| Café chatter, 0 dB | 6 / 28 | 10 / 28 | 8 / 28 |
| Static, 5 dB | 22 / 28 | 22 / 28 | 22 / 28 |
| Static, 0 dB | 10 / 28 | 13 / 28 | 13 / 28 |
| **Total** | 55 / 112 | **64 / 112** | 63 / 112 |

Greedy decoding was about 2.5x faster on clean audio but clearly worse in noise
(we first switched to it for speed, and a tester in a noisy room noticed it got
worse). The app uses **beam search with 3 beams**: as accurate as the default and a
little faster. Output is capped at 64 tokens so unclear audio can't make Whisper
loop, and each recording is transcribed only once, not again on every click.
Chatter is the hardest noise, because Whisper tries to transcribe the other voices.

#### Background music with lyrics (`coach/music.py`)

A tester in a café found that music with lyrics still broke speech recognition.
Noise filters can't help much here, because a singer *is* speech. We tested each
phrase with 1.5 s of music before and after it (a chord-and-beat track plus
sung-style Korean and English lyrics):

| Fix | Voice 10 dB louder | 5 dB louder | As loud as music |
| --- | --- | --- | --- |
| None | 27 / 28 | 23 / 28 | 12 / 28 |
| Loudness gate (keep only the loudest parts) | 28 / 28 | 21 / 28 | 13 / 28 |
| Noise filter (`noisereduce`) | 27 / 28 | 19 / 28 | 13 / 28 |
| Find the phrase inside the transcript | 27 / 28 | 26 / 28 | 22 / 28 |
| **+ scenario phrases as a hint for Whisper** | **28 / 28** | **28 / 28** | **27 / 28** |

The gate and the noise filter barely helped, so they are not used. The real problem
was that Whisper wrote the lyrics down *with* the phrase. A hint can make a model
"hear" what it expects, so we also played the *wrong* phrase for every target. With
the hint, no wrong answer was accepted. The one false acceptance we found came from a
first version of the transcript search: "충전해 주세요" inside "만 원 충전해 주세요" was
accepted for "교통카드 충전해 주세요". Now the matched words must be at least 75% as long
as the phrase. `coach/music.py` reruns this test with the app's own code
(final numbers below).

Final check with the app's own code (`coach/music.py`, Supertonic voices). "Wrong"
plays a different phrase from the same scenario, skipping phrases that contain an
accepted form (the first run counted "만 원 충전해 주세요" as wrong for "교통카드 충전해 주세요",
but the card accepts "충전해 주세요", so it is a fair answer):

| Voice vs. music | Plain check: right / wrong accepted | + find in transcript | **+ careful hint (app)** |
| --- | --- | --- | --- |
| 10 dB louder | 24 / 0 | 28 / 0 | **28 / 0** |
| 5 dB louder | 24 / 0 | 28 / 0 | **28 / 0** |
| As loud | 17 / 0 | 27 / 0 | **27 / 0** |

(out of 28 each)

**The hint invented answers from nothing at first.** Testing the recorder with a fake
microphone that played only a steady tone, Whisper "heard" 아이스 아메리카노 한 잔 주세요
and the app said *exactly right*: given the lesson's phrases as a hint and no real
speech, Whisper fills the gap with one of them. Our wrong-answer test had only played
*wrong speech*, never *no speech*. Now Whisper first listens without the hint; the
hinted second try counts only if the plain transcript already contains at least half
of the phrase's sounds (`checker.check_spoken`). The test now also plays sounds with
no learner speech for every target:

| No learner speech | Accepted as an answer |
| --- | --- |
| Steady tone | 0 / 28 |
| Fan-like noise | 0 / 28 |
| Music only (a singer, no learner) | 0 / 28 |

The generated voices are clean, native-like speech, so this is a best case.
Even here Whisper wrote 적립 as 정립 (how it sounds) and heard 부산외대에서 as
부산에 대해서. Both still passed as "close", but names and sound changes are its
weak spots. Next step: record classmates saying each phrase, save them as
`data/recordings/<phrase id>.wav` (e.g. `cafe_card.wav`), and run:

```bash
uv run python dev/evaluate_speech.py --recordings
```

### Choosing the speech model (`dev/compare_asr.py`)

Whisper-small was our day-one default, so we compared it with two newer open models on the
app's own tests (identical audio, the app's real grading). Speed is measured on 2 CPU cores,
like the free Hugging Face Space:

| | Whisper small (current) | Whisper large-v3-turbo | Qwen3-ASR 0.6B |
| --- | --- | --- | --- |
| Clean phrases | 91 / 91 | 91 / 91 | 91 / 91 |
| Music, voice 5 dB louder (right / wrong accepted) | 27 / 0 | **28 / 0** | 24 / 0 |
| Music, as loud as the voice | 22 / 0 | **26 / 0** | 20 / 0 |
| No speech (tone, fan, music) accepted | 0 | 0 | 0 |
| Invents text from silence? | yes ("아 아 아…") | yes ("다음 영상에서 만나요") | **no** (heard nothing) |
| Seconds per answer, 2 CPU cores | 2.1 | **~65** | **0.66** |
| Memory | 1.7 GB | 1.8 GB | 3.7 GB |
| Setup | in the app | in the app | needs its own package (`qwen-asr`, older transformers) |

- **Turbo** is the most accurate in loud music, but on a CPU it takes over a minute per answer:
  Whisper always processes a padded 30-second window, and turbo pushes it through the full
  large-v3 encoder. Usable only with a GPU.
- **Qwen3-ASR** is 3× faster than Whisper-small and doesn't invent text from silence, but it's
  weaker in loud music, and it needs a separate environment.
- **Whisper-small** stays the default: the best balance on free hardware.
- **Then faster-whisper took over (November 2026).** The same Whisper small model on the
  CTranslate2 engine (`whisper-small-fast`), tested with `dev/compare_asr.py` like the others:

  | | Whisper small (transformers) | Whisper small (faster-whisper) |
  | --- | --- | --- |
  | Clean phrases | 91 / 91 | 91 / 91 |
  | Music 5 dB below the voice | 27 / 28 | 27 / 28 |
  | Music as loud as the voice | 22 / 28 | **26 / 28** |
  | Wrong answers / answers from silence | 0 / 0 | 0 / 0 |
  | Memory | 1.5 GB | **0.9 GB** |

  It uses 8-bit maths on Intel/AMD servers (where that's fastest) and full precision on Apple
  silicon, where 8-bit measured slower (3.0 vs 1.75 s per answer on 2 cores). The original
  transformers engine stays available locally for comparison.
- **All three are in the app as a showcase.** The sidebar's *Speech model* picker shows each
  model's pros and cons. The **🔬 Model lab** page (team password online) runs one recording through several models
  side by side: a sample phrase or your own voice, optionally with café music mixed in. It
  shows what each model heard, how long it took, and whether the answer passes. Qwen3-ASR runs
  as a helper process in its own environment (`qwen/worker.py`, `qwen/requirements.txt`),
  because it needs an older `transformers` than the app. (Music numbers differ
  slightly from `coach/music.py` because the music is placed at different random points; all
  three models here got identical audio.)

### Learning

- **Pre-test / post-test** (built in): each lesson's 📝 Test tab asks every phrase from
  its English meaning, with no hints and no feedback until the end, once before studying
  and again after. The Progress page shows each scenario's gain (e.g. 22% → 89%, +67).
  Only exact or nearly exact phrases count, the same rule as Recall, and tests don't
  change the review schedule. Results: `data/tests.json` (`coach/learning_tests.py`).
- **Recall accuracy over time** (built in): the Progress page charts each day's share of
  correct Recall and Review answers. Because spaced repetition brings back the hard
  phrases more often, a flat line can still mean progress.
- **Feedback survey** (built in, 💬 Feedback page, anonymous): the **System Usability
  Scale** (SUS, Brooke 1996), the standard 10-question usability survey scored 0-100
  (68 = average across many studies, above 80 = top 10%), plus three questions on
  learning (are the scenarios real for students in Busan, do learners feel more
  confident, does speaking practice help) and two open questions. Results appear on the
  same page (`coach/survey.py`, `data/feedback.json`). Next step: ask a few classmates to do a
  lesson with the pre-test and post-test, then fill in the survey.

## Noisy surroundings

Every spoken answer is also measured for background noise (`speech.surroundings()`): the quietest
30 ms frames are the background, the loudest the voice. When the background is louder than
−45 dBFS and less than 20 dB below the voice, a banner says **"Noisy surroundings detected"**
(under 10 dB: **"Very noisy"**, with a tip to move, hold the microphone closer or switch to
⌨️ Type), and a wrong answer adds "it was noisy, so the AI may have misheard you".

The thresholds come from the app's own noise tests (30 phrases each):

| Recording | Flagged |
| --- | --- |
| Quiet room, normal or very soft voice | never |
| Café music 15 dB below the voice | 2 / 30 noisy |
| Café music 10 dB below | 30 / 30 noisy |
| Café music 5 dB below (Whisper still gets 27/28) | 30 / 30 noisy |
| Café music as loud as the voice (Whisper gets 22/28) | 26 very noisy, 4 noisy |

"Noisy" is an early heads-up: a real room with café noise measured −40 dBFS with the voice 16 dB
above it, and recognition still worked. "Very noisy" means it will probably mishear. On your own
computer, a 🔧 dev line under each spoken answer shows the measurement.

The banner goes away when a later recording is quiet, or with its ✕.

## Languages: English and 日本語

Everything a learner sees comes in **English or Japanese**: a switch at the top of the sidebar,
remembered in the address (`?lang=ja`, so a link can open straight in Japanese). On a first
visit the app follows the browser's language. Korean, romanization and the voices never change.

- **App text:** `T("English text")` in `app.py`, with the Japanese in `coach/i18n.py`. A missing
  translation simply shows the English.
- **Lesson content:** `data/scenarios_ja.json` holds the Japanese meaning, grammar note, common
  mistake, role-play prompt and task for every item, keyed by the ids in `scenarios.json`. The notes
  are adapted for Japanese speakers, not translated word for word: 잔 is compared to 杯, 은/는 to
  は, and 잘 부탁드려요 to よろしくお願いします.
- **Status:** the Japanese is AI-translated and shows a "確認中" note in the banner until a native
  speaker has checked it. The team-only areas (Model lab, survey results) stay in English.

## Run

To put it online (no sign-in; progress stays in each learner's browser, and one team password
unlocks the survey results and the Model lab), see [DEPLOY.md](DEPLOY.md).


```bash
uv sync
uv run streamlit run app.py
```

The first AI check downloads the meaning model (about 440 MB) and the first spoken
answer downloads Whisper (about 1 GB) from Hugging Face. The microphone works on
`localhost` (or HTTPS).

Making voice lines (`dev/make_audio.py`):

```bash
uv run python dev/make_audio.py                    # only missing audio, e.g. a new scenario
uv run python dev/make_audio.py --force-unchecked  # redo lines nobody has checked by ear yet
uv run python dev/make_audio.py --force            # redo everything, even lines already checked
```

A line counts as **checked** when someone listened and approved that exact text and audio file
(🎧 Voice check page, or marked by the owner; stored in `data/voice_review.json` with a
fingerprint of the file). Changing the text or regenerating the audio makes it unchecked again.
So far the owner has checked all 133 Situation (dialogue) lines by ear.

## Project layout

```
app.py              the Streamlit app: pages, lessons, review, progress, Model lab
coach/              the building blocks the app uses
  checker.py          spelling check and fact rules for Korean answers
  semantic.py         AI meaning check (Korean sentence embeddings)
  speech.py           speech recognition: Whisper small / turbo, Qwen3-ASR
  srs.py              Leitner spaced repetition
  learning_tests.py   pre-test / post-test and checkpoint results, learning gains
  survey.py           feedback survey (SUS usability score + learning questions)
  i18n.py             English / Japanese: the language switch and the app's Japanese text
  warmup.py           loads the AI models in the background when a lesson opens
  music.py            café music with sung lyrics, for noise tests and the Model lab
assets/             look and browser parts: style.css, style-light.css,
                    conversation_player.html, time_attack.js/.css, browser_store.js
data/
  scenarios.json      scenarios, dialogues, phrases, role-plays
  scenarios_ja.json   Japanese translations of all lesson content
  levels.json         levels, checkpoints (story role-plays), coming-soon scenarios
  audio/              voice lines (MP3) and the joined conversation tracks
  noise/              sung lyric lines for the music test
  asr_comparison/     speech model test results shown in the Model lab
qwen/               Qwen3-ASR helper process and its own requirements
docs/               HOW_IT_WORKS.md (this page), PROCESS.md (how it was built), DEPLOY.md (putting it online)
Dockerfile, start.sh   the full three-model version for Hugging Face Spaces
packages.txt        system packages for Streamlit Community Cloud (ffmpeg)
.streamlit/         theme (config.toml) and an example secrets file
```

**Kept on the developer's computer only** (in `.gitignore`, so not in this repository):
`dev/`, with the voice maker (`make_audio.py`), the evaluation scripts (`evaluate*.py`,
`compare_asr.py`), the voice review (`voice_review.py`, the 🎧 Voice check page) and their data
(`data/voice_review.json`, `data/voice_checks.json`, `data/eval_answers.json`,
`data/audio/variants/`). Learners' progress is never stored in the repository either.
