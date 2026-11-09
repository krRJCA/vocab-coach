# How we built Scenario Vocab Coach

The story of the project, step by step: what we decided, what we tried, what went wrong,
and how we fixed it. For how the app works in detail, see [README.md](../README.md); for putting
it online, see [DEPLOY.md](DEPLOY.md).

---

## At a glance

| | |
| --- | --- |
| **What it is** | A Korean learning app for international students in Busan: real situations, not word lists |
| **Content** | 10 scenarios in 2 levels, 91 phrases, 64 role-play turns, 1 checkpoint |
| **AI used** | Speech → text: Whisper small (default), Whisper turbo, Qwen3-ASR; a Korean meaning model (paraphrase check); Supertonic (natural voices) |
| **Built with** | Python, Streamlit, Hugging Face models, Docker |
| **How we kept it honest** | Every feature was measured: 175 labelled answers, 428 voice recordings checked, noise tests, a listener's ear |

---

## The journey in 19 steps

### 1. Choosing the idea
- Started from the class slide *"From AI Tools to Real Projects"* (five ways to use AI).
- Picked a **vocabulary app**, with one condition: it had to be *actually useful*, based on
  research, and about **real situations**, not single words.
- Decided the users: **international students at BUFS learning Korean**.

### 2. Planning before building
- Wrote a plan first: content format, files, learning loop, how to test it.
- Grounded the design in learning research (see the README table):
  - **Retrieval practice:** recalling beats rereading.
  - **Spaced repetition:** reviews spread out over days.
  - **Lexical chunks:** whole phrases, not single words.
  - **Task-based role-plays:** use the phrases for a real goal.
  - **Interleaving:** mixed review across scenarios.

### 3. Version 1: the learning loop
- 3 scenarios: café, getting around Busan, part-time job interview.
- Each lesson has four steps:
  - **Situation:** a model dialogue.
  - **Notice:** phrase cards with notes and common mistakes.
  - **Recall:** type the Korean from the English.
  - **Role-play:** a new conversation in the same situation.
- **Spaced repetition** (Leitner boxes): phrases come back after 1, 2, 4, 7, then 15 days.
- **Forgiving spell-check:** Korean is compared letter by letter (jamo), so 주새요 counts as
  "almost" 주세요.

### 4. Testing the answer checker, and finding it was wrong
- Wrote **75 realistic learner answers**, each labelled right or wrong, and measured the checker.
- **Problem:** the spell-checker accepted **6 of 28 wrong answers**: 이만 원 for 만 원, and
  아이스 라떼 when the task said a *hot* latte.
- **Fix:** **fact rules**. Close spellings must keep the same numbers, the same negation
  (돼요 vs 안 돼요) and the task's key words.

### 5. Adding AI to accept paraphrases
- Learners say things in many correct ways, so we added a **meaning model** (sentence
  embeddings from Hugging Face).
- **The first model failed:** it said 먹고 갈게요 (for here) and 가져갈게요 (to go) were 99.5%
  the same.
- **Switched to a Korean-specific model** (`ko-sroberta`): accuracy rose from 53% to **96%**, with
  **0 wrong answers accepted**.
- **Lesson:** AI alone isn't enough. The model still mixed up 아이스 and 따뜻한, and the simple
  fact rules caught it.

### 6. Voice: hearing and speaking
- Every line got a **recorded voice** (text-to-speech).
- Learners can **speak** their answers: Whisper turns speech into text, then the same checks run.
- **Bug found:** on silence, Whisper invents sentences like "시청해주셔서 감사합니다". We added a
  silence guard.

### 7. Faster, but not worse
- Speaking felt slow, so we switched Whisper to its fastest setting (greedy decoding):
  about 3× faster.
- **A tester noticed it got worse in a noisy room.** We measured: in noise, greedy decoding was
  clearly worse.
- **Fix:** a middle setting (beam search, 3 beams). As accurate as before, and not slower.
- **Also fixed:** a recording was being re-transcribed on every click.

### 8. Noise and music
- Tested speech with café chatter, static, and **music with lyrics**.
- **Noise filters didn't help.** Whisper *did* hear the learner; it just also wrote down the
  song lyrics.
- **Fix:** find the phrase *inside* the transcript, and give Whisper the lesson's phrases as a hint.
- **Bug found with a fake microphone:** a plain tone was "heard" as 아이스 아메리카노 한 잔 주세요
  and marked *exactly right*. The hint was inventing answers out of nothing.
- **Fix:** the hint is only a careful second try, accepted only if the plain transcript already
  has half the phrase's sounds. Now **0 of 28** accepted for a tone, fan noise or music alone,
  and **27 of 28** right answers still pass with music as loud as the voice.

### 9. Making it look good
- A Busan theme: camellia pink (동백꽃, the city flower), harbor navy, Korean fonts, and both
  light and dark modes.
- A big round record button like in chat apps, a styled sidebar, and an "Under construction"
  notice.
- Tabs for pages, phrase cards in one column, and "Exactly right" shown in clear green.

### 10. Making conversations sound like conversations
- Separate voice clips sounded disconnected: long silences and a slow pace.
- **Fix:** trimmed silences and joined each dialogue into one track, with a player that
  highlights the line being spoken.

### 11. Question intonation: measuring isn't listening
- Some questions sounded like statements, so we raised the pitch at the end with a phonetics
  tool (Praat).
- **The pitch meter said it worked; the listener said it sounded exaggerated.**
- **Lesson:** built a **two-step review process** for every voice line:
  1. **Automatic checks:** Whisper must understand it, with no gaps and no distortion.
  2. **A person listens** on the 🎧 Voice check page and approves it.

### 12. Better voices, without sign-ups
- The voices still sounded a bit robotic. The best options (Google, ElevenLabs) needed accounts.
- Found **Supertonic**, an open-source voice by a Korean company that runs on the laptop.
- **Pilot on one scenario:** it passed every check, and Whisper heard **5 of 6** questions as
  questions (vs 3 of 6 before). We switched.
- **The checks caught its mistakes:** digits read wrongly (5번), 앉으세요 heard as "안 주세요",
  and 식후 heard as "19". Each was fixed with a pronunciation hint, for the voice only.

### 13. Time attack: real conversation speed
- A second role-play mode: their line plays, the recorder **starts by itself**, and you have a
  few seconds to answer.
- **Time limit:** 1.5 s to react, plus the length of a good answer at learner speed
  (2.5 syllables per second), between 3 and 10 seconds.
- Each answer shows how fast you started answering (2 seconds or less counts as natural).

### 14. Is this needed in Busan?
- Researched what Busan already offers: free classes (Busan Global City Foundation,
  부산한글학당) and national apps (King Sejong Institute).
- **Gap found:** no Busan-specific self-study app for students' real first-week situations.
- **Goal:** a companion to the city's classes.

### 15. More content, levels and a checkpoint
- Grew to **10 scenarios**, adding:
  - 🍜 restaurant
  - 🏪 convenience store
  - 🐟 Jagalchi market
  - 💊 pharmacy
  - 🤝 making friends
  - 🏠 dorm
  - 🏫 campus office
- **Level 1** (8 survival scenarios, about TOPIK 1), then a **🏁 Checkpoint**: a 16-phrase
  mixed test with an 80% pass mark, plus a story role-play. Then **Level 2** (TOPIK 2).
- **Measuring learning:**
  - A **pre-test and post-test** for every lesson, giving the learning gain.
  - **Accuracy over time** on the Progress page.
  - A **feedback survey**: the standard usability score (SUS) plus learning questions.
- **Every new scenario got labelled answers, which found more bugs:**
  - The number rule read 다시 **한**번 ("once again") as the number 1.
  - Whisper writes numbers as digits (2명, 4,500원), so correct spoken answers failed.
  - The AI accepted 택배 **보내러** (to send) for picking up a parcel, and 몇 시**까지** (until)
    for 몇 시**부터** (from).
- **Result:** 175 labelled answers, **98%** accuracy, **0 of 69** wrong answers accepted.

### 16. A good ear beats automatic checks
- **The user heard endings being cut off** (학생증 있으세요?). The silence trimming was cutting
  soft final syllables.
- **Fixed** the trimming and regenerated all 203 dialogue lines.
- **The user heard a missing 요** in 어느 나라에서 왔어요?. The voice had skipped it.
- Whisper still "understood" both, so the checks passed them. **Added a new check: last
  syllable missing.**
- **Result:** all **428 recordings pass**, and the speech test passes **91 of 91** phrases.

### 17. Keeping track of what a person has heard
- The owner listened to all 133 Situation lines. Each is marked "checked" with its text and a
  fingerprint of the exact audio file heard.
- `dev/make_audio.py --force-unchecked` regenerates only lines nobody has checked; `--force` redoes
  everything. A regenerated or edited line becomes unchecked again automatically.

### 18. Comparing newer speech models, and a model showcase
- Whisper-small was a day-one default, so we tested it against two newer open models on the
  app's own tests:
  - **Whisper large-v3-turbo:** most accurate in loud music (26 / 28), but about a minute per
    answer on a CPU.
  - **Qwen3-ASR:** the fastest (0.66 s) and never invents words from silence, but weaker in
    noise (20 / 28).
- **Whisper-small** (22 / 28, 2.1 s) stayed the default.
- All three became a **showcase**: the sidebar shows each model's pros and cons, and the
  **🔬 Model lab** compares them on the same recording. With loud café music, Whisper heard the
  phrase and Qwen heard the song lyrics.

### 19. Easier to use, then ready to deploy
- **Navigation:**
  - ← All lessons, ‹ Previous / Next › buttons, and "Continue →" at the end of each lesson.
  - A Level picker for lessons.
  - A clearer "to review" counter.
- **Deployment:**
  - First built **Sign in with Google**, then chose **no sign-in** to keep it easy: each
    learner's progress is saved in their own browser, and the notice says so.
  - One **team password** for the survey results and the Model lab.
  - **Dev-only tools** (Voice check, marked ᵈᵉᵛ) live in `dev/voice_check.py`, which never leaves
    the laptop.
  - Answers say **"Whisper heard"** or **"Qwen heard"**, so learners see which AI listened.
  - Packaged with Docker for Hugging Face Spaces (free, 16 GB of memory), with a smaller
    CPU-only version of PyTorch.
  - The image was built and tested locally: the models work with no internet.
  - **Plan B:** Hugging Face made Docker Spaces paid (PRO) in 2026, so the free version moved to
    **Streamlit Community Cloud** with Whisper small only (~0.8 GB of memory). The app notices
    where it runs and switches by itself; the full three-model version still runs with PRO.

---

## What we learned

1. **Measure everything.** Almost every improvement started with a number that looked wrong.
2. **But listen too.** Pitch meters and Whisper said "fine" while a person heard exaggerated
   questions, clipped endings and a missing 요.
3. **AI needs simple rules next to it.** The meaning model confused hot and iced, send and pick
   up. A few key-word rules fixed what the AI missed.
4. **Test what should fail, not only what should pass.** The worst bug (answers invented from
   silence) only appeared when we tested with *no* speech.
5. **Faster isn't always better.** The fastest speech setting was worse in real, noisy rooms.
6. **Start small, then grow.** 3 scenarios, then 6, then 10 in levels, with the same checks
   every time.

---

## What's next

- **A native speaker** checks the Korean content and approves voices on the 🎧 Voice check page.
- **Real classmates test it:** recorded answers, pre/post tests, and the feedback survey.
- **Put it online** with Google sign-in (see [DEPLOY.md](DEPLOY.md)), optionally saving progress
  to a private Hugging Face dataset.
- **Build Level 2:** bank, phone plan, doctor, renting, group project, refunds, then Checkpoint 2.
