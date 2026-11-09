"""Scenario Vocab Coach: learn Korean phrases inside real situations.

Each lesson is a scenario (café, getting around Busan, job interview) with
the phrases you need for it. You recall each phrase from memory, use it in
a role-play, and a Leitner spaced-repetition schedule brings it back
just before you would forget it. An optional AI meaning check accepts
answers that use different words but mean the same, and answers can be
typed or spoken (Whisper speech recognition). Every line has a voice recording.
"""

import base64
import io
import hashlib
import hmac
import os
import json
import random
import re
import time
from html import escape
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from coach import learning_tests, semantic, speech, srs, survey, warmup
from coach.i18n import LANGUAGES, L, T, add_japanese, lang
from coach.checker import check, check_spoken
from coach.icons import svg

try:  # dev-only tools (Voice check) live in dev/voice_check.py, which is never deployed
    from dev import voice_check as dev_tools
except ImportError:
    dev_tools = None

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
SCENARIOS_PATH = DATA_DIR / "scenarios.json"
AUDIO_DIR = DATA_DIR / "audio"
ASSETS_DIR = APP_DIR / "assets"
STYLE_PATH = ASSETS_DIR / "style.css"
LIGHT_STYLE_PATH = ASSETS_DIR / "style-light.css"
PLAYER_PATH = ASSETS_DIR / "conversation_player.html"
SPEAKER_AVATARS = {"나": "🙋"}
TYPE, SPEAK = "⌨️ Type", "🎙️ Speak"


@st.cache_data
def load_scenarios():
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


SCENARIOS = load_scenarios()
SCENARIO_BY_ID = {scenario["id"]: scenario for scenario in SCENARIOS}
LEVELS = json.loads((DATA_DIR / "levels.json").read_text(encoding="utf-8"))
add_japanese(SCENARIOS, LEVELS)  # Japanese fields from data/scenarios_ja.json
LEVEL_NUMBER = {sid: number for number, level in enumerate(LEVELS, 1) for sid in level["scenarios"]}
CHECKPOINT_BY_ID = {level["checkpoint"]["id"]: (number, level)
                    for number, level in enumerate(LEVELS, 1) if level.get("checkpoint")}
CHUNK_BY_ID = {
    chunk["id"]: (chunk, scenario)
    for scenario in SCENARIOS
    for chunk in scenario["chunks"]
}


# ---------- Sign-in and per-user storage ----------


def login_enabled():
    """Google sign-in is on when .streamlit/secrets.toml has an [auth] section (when deployed)."""
    try:
        return "auth" in st.secrets
    except Exception:  # no secrets file: running locally
        return False


def user_email():
    return st.user.email if login_enabled() and st.user.is_logged_in else None


def online():
    """True when deployed: Streamlit Community Cloud, Hugging Face Spaces (it sets SPACE_ID), or
    VOCAB_ONLINE=1 to try the online behaviour on your own computer."""
    return bool(os.environ.get("SPACE_ID") or os.environ.get("VOCAB_ONLINE")) or speech.on_streamlit_cloud()


def storage_mode():
    """Where progress and test results live:
    "server": with Google sign-in, one folder per account on the server;
    "browser": online without sign-in, in each learner's own browser (localStorage);
    "local": on this computer, in data/ (VOCAB_STORAGE=browser tries the browser mode locally)."""
    if login_enabled():
        return "server"
    if online() or os.environ.get("VOCAB_STORAGE") == "browser":
        return "browser"
    return "local"


def dev_mode():
    """Dev-only pages (Voice check) appear only on your own computer, never online."""
    return dev_tools is not None and not online()


DEV_MARK = " ᵈᵉᵛ"  # small raised "dev" after a dev-only page's name


def voice_check_page():
    dev_tools.voice_check_page(html, by=user_email() or "team")


def is_admin():
    """Team members (secrets: admins = ["you@gmail.com"]) see the survey results and Model lab
    without the team password.
    Locally, without sign-in, you are the admin. Online without sign-in, nobody is: the team
    pages would otherwise be open to every visitor."""
    if not login_enabled():
        return not online()
    try:
        admins = [email.lower() for email in st.secrets.get("admins", [])]
    except Exception:
        admins = []
    return (user_email() or "").lower() in admins


def user_dir():
    """Each signed-in user's own folder (named by a hash of their email, not the email itself).
    Locally, without sign-in, progress stays in data/ as before."""
    email = user_email()
    if not email:
        return DATA_DIR
    folder = DATA_DIR / "users" / hashlib.sha256(email.lower().encode()).hexdigest()[:16]
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def progress_path():
    return user_dir() / "progress.json"


def tests_path():
    return user_dir() / "tests.json"


BROWSER_STORE = st.components.v2.component(
    "browser_store", js=(ASSETS_DIR / "browser_store.js").read_text(encoding="utf-8")
)


def load_from_browser():
    """Browser mode: get this browser's saved progress before any page uses it."""
    state = st.session_state
    if storage_mode() != "browser" or "_browser_version" in state:
        return
    result = BROWSER_STORE(key="browser-load", data={"mode": "load"}, on_loaded_change=lambda: None)
    saved = getattr(result, "loaded", None)
    if saved is None:  # the browser answers on the next run
        st.caption(T("Loading your progress…"))
        st.stop()
    state.progress = saved.get("progress") or {}
    state.tests = saved.get("tests") or {}
    state._browser_version = state._browser_saved = saved.get("version", 0)


def save_to_browser():
    """Browser mode: send changed progress to the browser (runs at the end of every page)."""
    state = st.session_state
    if storage_mode() != "browser":
        return
    pending = state.get("_browser_version", 0) > state.get("_browser_saved", 0)
    BROWSER_STORE(key="browser-save", data={"save": {
        "version": state.get("_browser_version", 0), "progress": progress(), "tests": load_tests(),
    }} if pending else {})
    state._browser_saved = state.get("_browser_version", 0)


def changed_in_browser():
    st.session_state._browser_version = st.session_state.get("_browser_version", 0) + 1


def load_tests():
    if storage_mode() == "browser":
        return st.session_state.setdefault("tests", {})
    return learning_tests.load(tests_path())


def save_tests(tests):
    if storage_mode() == "browser":
        st.session_state.tests = tests
        changed_in_browser()
        return
    learning_tests.save(tests, tests_path())


def progress():
    if "progress" not in st.session_state:
        st.session_state.progress = {} if storage_mode() == "browser" else srs.load(progress_path())
    return st.session_state.progress


def save_progress():
    if storage_mode() == "browser":
        changed_in_browser()
    else:
        srs.save(progress(), progress_path())


def record(chunk_id, correct):
    srs.record(progress(), chunk_id, correct)
    save_progress()


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def icon_steps(steps, more=None):
    """Instructions as a row of icon chips (icon, short label) instead of a paragraph.
    more: the full explanation, behind a small ⓘ that opens on tap (hover tooltips don't
    work on phones)."""
    chips = '<span class="icon-arrow">›</span>'.join(
        f'<span class="icon-step">{svg(icon)}<span>{escape(label)}</span></span>' for icon, label in steps
    )
    extra = ""
    if more:
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(more))
        extra = f'<details class="more"><summary title="{escape(T("More"))}">i</summary><div>{text}</div></details>'
    html(f'<div class="icon-steps">{chips}{extra}</div>')


def go(page, scenario_id=None):
    """Open another page (a tab in the top navigation)."""
    if scenario_id:
        st.session_state.scenario = scenario_id
    st.switch_page(PAGES[page])


def play(name, autoplay=False):
    """Play a pre-generated voice line from data/audio (see dev/make_audio.py)."""
    path = AUDIO_DIR / f"{name}.mp3"
    if path.exists():
        st.audio(str(path), format="audio/mpeg", autoplay=autoplay)


def conversation_player(scenario, romanization, english):
    """The dialogue as one connected recording, highlighting each line as it is spoken.

    Falls back to one player per line if the joined track has not been made yet.
    """
    track = AUDIO_DIR / f"{scenario['id']}_conversation.mp3"
    timings = track.with_suffix(".json")
    if not (track.exists() and timings.exists()):
        return False
    data = {
        "audio": "data:audio/mpeg;base64," + base64.b64encode(track.read_bytes()).decode(),
        "timings": json.loads(timings.read_text(encoding="utf-8")),
        "lines": [{**line, "en": L(line, "en")} for line in scenario["dialogue"]],
        "romanization": romanization,
        "english": english,
        "labels": {text: T(text) for text in ("Play the whole conversation", "Play conversation", "Pause",
                                              "Repeat this line", "Playback speed")},
        "dark": st.context.theme.type == "dark",
    }
    markup = PLAYER_PATH.read_text(encoding="utf-8").replace(
        "__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    )
    st.iframe(markup, height="content")
    return True


@st.cache_resource(show_spinner=False)
def ai_model():
    warmup.wait("meaning")  # a lesson may already be loading it in the background
    return semantic.load_model()


def asr_engine():
    """The speech model picked in the sidebar."""
    engine = st.session_state.get("asr_engine") or speech.DEFAULT_ENGINE
    return engine if speech.is_available(engine) else speech.DEFAULT_ENGINE


@st.cache_resource(show_spinner=False)
def _load_speech_model(engine):
    warmup.wait(f"speech-{engine}")  # a lesson may already be loading it in the background
    return speech.load_model(engine)


def preload_models():
    """Start loading the models this learner will need, in the background (see coach/warmup.py):
    the speech model only if they answer by speaking, the meaning model only if it's on."""
    if st.session_state.get("answer_mode", SPEAK) == SPEAK and speech.is_available(asr_engine()):
        engine = asr_engine()
        warmup.preload(f"speech-{engine}", lambda: speech.load_model(engine))
    if st.session_state.get("ai_check", True) and semantic.is_available():
        warmup.preload("meaning", semantic.load_model)


def speech_model(engine=None):
    engine = engine or asr_engine()
    with st.spinner(T("Loading {model} (first time only)…", model=speech.ENGINES[engine]['label'])):
        return _load_speech_model(engine)


def transcribe(audio, hint=""):
    """Speech → text with the sidebar's model."""
    engine = asr_engine()
    speech_model(engine)
    return speech.transcribe(audio, hint=hint, engine=engine)


def engine_card(engine, compact=False):
    """Short pros and cons of a speech model."""
    info = speech.ENGINES[engine]
    lines = [f"**{info['label']}** · {info['tag']}", f"⏱️ {info['speed']}"]
    lines += [f"✅ {pro}" for pro in info["pros"]] + [f"⚠️ {con}" for con in info["cons"]]
    if compact:
        st.caption("  \n".join(lines))
    else:
        st.markdown("  \n".join(lines))


def answer_input(key, label, hint=""):
    """Type or speak an answer, depending on the sidebar choice.

    hint: the scenario's phrases, to help speech recognition in noisy places.

    Returns (text, spoken, hinted) once the learner submits, otherwise None.
    spoken is the speech model's name for spoken answers (False when typed); hinted is a
    function that re-runs that model with the hint.
    """
    if st.session_state.get("answer_mode") == SPEAK:
        recording = st.audio_input(T("{label}: tap the mic and say it in Korean", label=label), key=f"{key}-audio")
        if recording is None:
            return None
        # The recorder keeps its recording, so every later click reruns this:
        # transcribe each recording once and reuse the text.
        audio = recording.getvalue()
        keep_recording(key, audio, recording.type or "audio/wav")
        heard = st.session_state.get(f"{key}-heard")
        if not heard or heard["audio"] != (hash(audio), asr_engine()):
            heard = {"audio": (hash(audio), asr_engine())}
            speech_model()
            with st.spinner(T("Listening…")):
                heard["plain"] = transcribe(audio)
            note_surroundings(audio)
            st.session_state[f"{key}-heard"] = heard

        def hinted():
            if "hinted" not in heard:
                with st.spinner(T("Listening again more closely…")):
                    heard["hinted"] = transcribe(audio, hint=hint)
            return heard["hinted"]

        if not heard["plain"]:
            if st.session_state.get("surroundings") in NOISE_MESSAGES:
                st.warning(T("I couldn't hear your words over the background noise. Try a quieter spot, or hold "
                             "the microphone closer."))
            else:
                st.warning(T("I couldn't hear anything. Try recording again, a little louder."))
            return None
        return heard["plain"], asr_engine(), hinted  # "spoken" = the model that heard it

    with st.form(key):
        text = st.text_input(label, key=f"{key}-input")
        submitted = st.form_submit_button(T("Check"), type="primary")
    return (text, False, None) if submitted and text.strip() else None


MAX_RECORDINGS = 40  # kept per visit, newest first out; each is ~50-150 KB


def keep_recording(key, audio, mime):
    """Keep a spoken answer so the learner can listen to themselves next to the model voice."""
    recordings = st.session_state.setdefault("recordings", {})
    recordings.pop(key, None)
    recordings[key] = (audio, mime)
    while len(recordings) > MAX_RECORDINGS:
        recordings.pop(next(iter(recordings)))


def noise_reading():
    """Dev only (on your own computer): what the noise check measured for the last recording,
    to calibrate it against real rooms. Thresholds: coach/speech.py."""
    reading = st.session_state.get("noise-reading")
    if not dev_mode() or not reading or reading[0] is None:
        return
    background, margin, level = reading
    st.caption(f"🔧 dev · noise check: background {background:.0f} dBFS (noisy above {speech.NOISE_FLOOR_DB}) · "
               f"voice {margin:+.1f} dB above it (noisy under {speech.NOISY_MARGIN_DB}) → **{level}**")


def my_recording(key):
    """▶ the learner's own recording for this answer, if they spoke it."""
    kept = st.session_state.get("recordings", {}).get(key)
    if kept:
        st.caption(T("🎙️ Your recording:"))
        st.audio(kept[0], format=kept[1])


def note_surroundings(audio, popup="dialog"):
    """Remember how noisy the learner's last recording was (see noise_banner).

    When it becomes noisy (or noisier), the next run also pops up a message, since the learner is
    usually scrolled down to their answer: a dialog, or a small toast during time attack."""
    try:
        background, margin, level = speech.noise_measure(audio)
    except Exception:
        return
    st.session_state["noise-reading"] = (background, margin, level)
    previous = st.session_state.get("surroundings")
    if level != previous:
        st.session_state.pop("noise-dismissed", None)  # a new level: show the banner again
        if level in NOISE_MESSAGES and NOISE_RANK[level] > NOISE_RANK.get(previous, 0):
            st.session_state["noise-popup"] = popup
    st.session_state["surroundings"] = level


NOISE_MESSAGES = {
    "noisy": "🔊 **Noisy surroundings detected.** The AI may mishear some words. A quieter spot, or holding "
             "the microphone closer, will help.",
    "very noisy": "🔊 **Very noisy surroundings.** The background is almost as loud as your voice, so the AI "
                  "will probably mishear you. Try a quieter spot, hold the microphone closer, or switch to "
                  "⌨️ Type in the sidebar.",
}


NOISE_RANK = {"quiet": 0, "noisy": 1, "very noisy": 2}


def use_typing():
    st.session_state["answer_mode"] = TYPE


def noise_popup(level):
    """A popup the moment noise is detected, wherever the learner has scrolled to."""
    @st.dialog(T("🔊 Noisy surroundings"))
    def popup():
        st.markdown(T(NOISE_MESSAGES[level]))
        typing, speaking = st.columns(2)
        if typing.button(T("⌨️ Switch to typing"), type="primary", width="stretch", on_click=use_typing):
            st.rerun()
        if speaking.button(T("Keep speaking"), width="stretch"):
            st.rerun()

    popup()


def noise_banner():
    """A warning at the top of the page while the learner's recordings are noisy.

    The slot is always there (empty when it's quiet): adding an element above the lesson tabs
    would make Streamlit rebuild them and jump back to the first tab."""
    slot = st.container(key="noise-slot")
    level = st.session_state.get("surroundings")
    popup = st.session_state.pop("noise-popup", None)
    if level in NOISE_MESSAGES and popup == "dialog":
        noise_popup(level)
    elif level in NOISE_MESSAGES and popup == "toast":
        st.toast(T("Noisy surroundings: the AI may mishear you."), icon="🔊")
    if level not in NOISE_MESSAGES or st.session_state.get("noise-dismissed"):
        return
    with slot.container(key="noise-banner"):
        text, close = st.columns([12, 1], vertical_alignment="center")
        text.warning(T(NOISE_MESSAGES[level]))
        if close.button("✕", key="noise-dismiss", help=T("Hide until the noise changes")):
            st.session_state["noise-dismissed"] = True
            st.rerun()


def scenario_hint(scenario):
    """All of a scenario's phrases: what the learner is likely to say."""
    return " ".join(chunk["ko"] for chunk in scenario["chunks"])


FOUND_NOTE = "Found your phrase among background sounds."


def grade(answer, accepted, keywords=(), hinted=None):
    """Spelling check first; if that fails, ask the AI whether the meaning matches.

    Spoken answers (hinted is given) are also searched for the phrase inside the
    transcript, because Whisper writes down background lyrics and voices too, and
    get a careful second try with the lesson phrases as a hint (see check_spoken).
    Returns (result, match, ai_note, heard) where result is
    "exact", "close", "meaning", or "wrong", and heard is the answer to show.
    """
    if hinted is not None:
        result, match, _, heard, how = check_spoken(answer, accepted, keywords, hinted)
        if how:
            return result, match, T(FOUND_NOTE), heard
    else:
        result, match, _ = check(answer, accepted, keywords)
    if result != "wrong" or not st.session_state.get("ai_check"):
        return result, match, "", answer
    with st.spinner(T("Loading the AI model (first time only)…")):
        ai_model()
    same, ai_match, score, reason = semantic.meaning_check(answer, accepted, keywords)
    if same:
        return "meaning", ai_match, T("AI meaning similarity {score}", score=f"{score:.2f}"), answer
    return "wrong", match, T("AI meaning similarity {score}: {reason}", score=f"{score:.2f}", reason=T(reason)), answer


def other_answers(accepted, match):
    """Every other accepted answer, so learners see more than one way to say it."""
    return [a for a in dict.fromkeys(accepted) if a != match]


def heard_by(spoken):
    """Friendly family name of the model behind a spoken answer: "Whisper" or "Qwen"
    (older answers just say True, and were all Whisper)."""
    return "Qwen" if str(spoken).startswith("qwen") else "Whisper"


def show_feedback(answer, result, match, ai_note="", echo=True, recall=False, spoken=False, accepted=()):
    if result == "exact":
        st.success(T("정확해요! Exactly right: **{match}**", match=match))
    elif result == "close":
        st.warning(T("Almost! Check the spelling: **{match}**", match=match))
    elif result == "meaning" and recall:
        st.info(T("Right meaning! The phrase we're practicing is: **{match}**", match=match))
    elif result == "meaning":
        st.success(T("자연스러워요! Different words, same meaning. Model answer: **{match}**", match=match))
    else:
        st.error(T("Not quite. A natural answer: **{match}**", match=match))
    if others := other_answers(accepted, match):
        st.caption(T("✅ Also correct: ") + " · ".join(others))
    if echo:
        st.caption(T("🎙️ {model} heard: {answer}", model=heard_by(spoken), answer=answer) if spoken
                   else T("You wrote: {answer}", answer=answer))
    if ai_note:
        st.caption(f"🎧 {ai_note}" if ai_note == T(FOUND_NOTE) else f"🤖 {ai_note}")
    if spoken and result == "wrong" and st.session_state.get("surroundings") in NOISE_MESSAGES:
        st.caption(T("🔊 It was noisy where you recorded, so the AI may have misheard you."))


# ---------- Recall ----------


def recall_card(chunk, scenario, key):
    """Ask for one phrase from memory. Returns True once it is answered."""
    hint_key, result_key = f"{key}-hint", f"{key}-result"
    used_hint = st.session_state.get(hint_key, False)

    html(
        f'<span class="pill">{scenario["icon"]} {escape(L(scenario, "title_en"))}</span>'
        f'<span class="pill accent">{escape(L(chunk, "register"))}</span>'
        f'<div class="prompt-label">{T("How do you say it in Korean?")}</div>'
        f'<div class="prompt-en">{escape(L(chunk, "en"))}</div>'
    )
    if used_hint:
        st.info(T("Hint: *{romanization}*", romanization=chunk['romanization']))

    if result_key not in st.session_state:
        submitted = answer_input(key, T("Your answer"), hint=scenario_hint(scenario))
        if st.button(T("Show hint"), key=f"{key}-hint-button", disabled=used_hint):
            st.session_state[hint_key] = True
            st.rerun()
        if submitted:
            answer, spoken, hinted = submitted
            accepted = [chunk["ko"], *chunk.get("alternatives", [])]
            result, match, ai_note, answer = grade(answer, accepted, hinted=hinted)
            # Recall practices this exact phrase, so a paraphrase is not yet "known".
            correct = result in ("exact", "close") and not used_hint
            record(chunk["id"], correct)
            st.session_state[result_key] = (answer, result, match, ai_note, correct, spoken)
            st.rerun()
        return False

    answer, result, match, ai_note, correct, spoken = st.session_state[result_key]
    show_feedback(answer, result, match, ai_note, recall=True, spoken=spoken,
                  accepted=[chunk["ko"], *chunk.get("alternatives", [])])
    if spoken:
        my_recording(key)
        noise_reading()
    st.caption(T("🔊 Listen and repeat:"))
    play(chunk["id"])
    if result == "meaning":
        st.caption(T("It will come back tomorrow so you can practice this exact phrase."))
    elif result != "wrong" and not correct:
        st.caption(T("You used the hint, so this phrase will come back tomorrow."))
    if result == "wrong":
        html(
            f'<div class="ko">{escape(chunk["ko"])}</div>'
            f'<div><i>{escape(chunk["romanization"])}</i></div>'
            f'<div class="mistake">⚠️ {escape(L(chunk, "common_mistake"))}</div>'
        )
    return True


def recall_session(chunk_ids, state_key, done_message):
    """Step through recall cards one at a time."""
    st.session_state.setdefault(f"{state_key}-index", 0)
    st.session_state.setdefault(f"{state_key}-round", 0)
    index = st.session_state[f"{state_key}-index"]
    round_ = st.session_state[f"{state_key}-round"]

    if index >= len(chunk_ids):
        st.success(done_message)
        if st.button(T("Practice again"), key=f"{state_key}-again"):
            st.session_state[f"{state_key}-index"] = 0
            st.session_state[f"{state_key}-round"] = round_ + 1
            st.rerun()
        return

    st.progress(index / len(chunk_ids), text=f"{index + 1} / {len(chunk_ids)}")
    chunk, scenario = CHUNK_BY_ID[chunk_ids[index]]
    if recall_card(chunk, scenario, key=f"{state_key}-{round_}-{index}"):
        if st.button(T("Next →"), type="primary", key=f"{state_key}-next"):
            st.session_state[f"{state_key}-index"] = index + 1
            st.rerun()


# ---------- Pages ----------


def level_state(number):
    """(post-tests done, checkpoint passed, unlocked) for level `number` (1-based)."""
    tests = load_tests()
    level = LEVELS[number - 1]
    done = sum(bool((tests.get(sid) or {}).get("post")) for sid in level["scenarios"])
    passed = bool(level.get("checkpoint")) and learning_tests.checkpoint_status(tests, level["checkpoint"])[2]
    previous = LEVELS[number - 2] if number > 1 else None
    unlocked = previous is None or not previous.get("checkpoint") or \
        learning_tests.checkpoint_status(tests, previous["checkpoint"])[2]
    return done, passed, unlocked


def scenario_card(scenario, locked):
    with st.container(border=True, key=f"card-{scenario['id']}"):
        html(
            f'<div class="card-icon">{scenario["icon"]}</div>'
            f'<p class="card-title">{escape(scenario["title_ko"])}</p>'
            f'<p class="card-sub">{escape(L(scenario, "title_en"))}</p>'
            f'<span class="pill">{T("{n} phrases", n=len(scenario["chunks"]))}</span>'
            f'<span class="pill">{T("{n}-turn role-play", n=len(scenario["roleplay"]))}</span>'
        )
        if st.button(T("Start anyway →") if locked else T("Start lesson →"), key=f"start-{scenario['id']}",
                     type="secondary" if locked else "primary", width="stretch"):
            go("Lesson", scenario["id"])


def checkpoint_card(number, level):
    checkpoint = level["checkpoint"]
    best, _, passed = learning_tests.checkpoint_status(load_tests(), checkpoint)
    items = checkpoint.get("test_per_scenario", 2) * len(level["scenarios"])
    with st.container(border=True, key=f"card-checkpoint-{number}"):
        status = (T("✅ Passed") if passed else T("Best so far: {best}", best=f"{best:.0%}") if best is not None
                  else T("Open anytime: also works as a placement test"))
        html(
            f'<div class="card-icon">{checkpoint.get("icon", "🏁")}</div>'
            f'<p class="card-title">{T("Checkpoint {n}", n=number)}</p>'
            f'<p class="card-sub">{escape(checkpoint["title_ko"])}</p>'
            f'<span class="pill">{T("{n}-phrase mixed test", n=items)}</span>'
            f'<span class="pill">{T("{n}-turn story", n=len(checkpoint["roleplay"]))}</span>'
            f'<span class="pill accent">{T("pass: {pct}", pct=f"{checkpoint.get("pass", 0.8):.0%}")}</span>'
            f'<p class="card-sub" style="margin-top:0.4rem">{status}</p>'
        )
        if st.button(T("Take the checkpoint →"), key=f"checkpoint-{number}", type="primary", width="stretch"):
            st.session_state.checkpoint = checkpoint["id"]
            st.switch_page(PAGES["Checkpoint"])


def planned_card(item):
    with st.container(border=True, key=f"card-planned-{item['title_en']}"):
        html(
            f'<div class="card-icon" style="opacity:.55">{item["icon"]}</div>'
            f'<p class="card-title" style="opacity:.6">{escape(item["title_ko"])}</p>'
            f'<p class="card-sub">{escape(L(item, "title_en"))}</p>'
            f'<span class="pill">{T("🚧 coming soon")}</span>'
        )


def level_section(number, level):
    done, passed, unlocked = level_state(number)
    total = len(level["scenarios"]) + len(level.get("planned", []))
    html(
        f'<div class="level-head"><span class="level-badge">{T("Level {n}", n=number)}</span>'
        f'<div><b>{escape(L(level, "title_en"))}</b> · {escape(level["title_ko"])}'
        f'<span class="pill">{escape(T("{level} · TOPIK {topik} level", level=L(level, "level"), topik=level["topik"]))}</span>'
        + (f'<span class="pill accent">{T("✅ complete")}</span>' if passed else "")
        + f'<div class="level-sub">{escape(L(level, "description"))} '
        f'{T("{done} / {total} lessons finished (post-test taken).", done=done, total=total)}</div></div></div>'
    )
    if not unlocked:
        st.caption(T("🔒 Recommended after Checkpoint {n}. You can still open any lesson.", n=number - 1))
    cards = [("scenario", SCENARIO_BY_ID[sid]) for sid in level["scenarios"]]
    cards += [("planned", item) for item in level.get("planned", [])]
    if level.get("checkpoint"):
        cards.append(("checkpoint", level))
    for row in range(0, len(cards), 3):
        for column, (kind, item) in zip(st.columns(3), cards[row:row + 3]):
            with column:
                if kind == "scenario":
                    scenario_card(item, locked=not unlocked)
                elif kind == "planned":
                    planned_card(item)
                else:
                    checkpoint_card(number, item)


def home_page():
    phrase_count = sum(len(scenario["chunks"]) for scenario in SCENARIOS)
    html(
        '<div class="hero">'
        f'<div class="hero-kicker">부산에서 바로 쓰는 한국어 · {T("REAL KOREAN FOR BUSAN")}</div>'
        "<h1>Scenario Vocab <span class=\"accent-word\">Coach</span></h1>"
        f"<p>{T('Learn the Korean you actually need in Busan: whole phrases inside real situations, practiced until you can say them without help.')}</p>"
        '<div class="hero-stats">'
        f"<span>{T('🎬 {n} scenarios in {levels} levels', n=len(SCENARIOS), levels=len(LEVELS))}</span>"
        f"<span>{T('💬 {n} phrases', n=phrase_count)}</span>"
        f"<span>{T('🔊 Natural Korean voices')}</span>"
        f"<span>{T('🎙️ Speak or type')}</span>"
        "</div></div>"
    )

    st.subheader(T("How a lesson works"))
    steps = [
        ("chat", T("Situation"), T("Listen to a real dialogue.")),
        ("notice", T("Notice"), T("Study the key phrases and common mistakes.")),
        ("recall", T("Recall"), T("Type or say each phrase from memory.")),
        ("roleplay", T("Role-play"), T("Use the phrases in a new conversation.")),
    ]
    html(
        '<div class="steps">'
        + "".join(
            f'<div class="step"><div class="step-icon">{svg(icon)}<span>{number}</span></div>'
            f"<b>{title}</b><small>{text}</small></div>"
            for number, (icon, title, text) in enumerate(steps, 1)
        )
        + "</div>"
    )

    for number, level in enumerate(LEVELS, 1):
        level_section(number, level)

    with st.expander(T("⌨️ How to type Korean")):
        st.markdown(T(
            "- **Mac:** System Settings → Keyboard → Text Input → Edit → **+** → Korean → 2-Set Korean\n"
            "- **Windows:** Settings → Time & Language → Language → Add a language → Korean\n"
            "- **Phone:** add the Korean keyboard in your keyboard settings\n\n"
            "Romanization is only a hint. Typing real Hangul is part of the practice."
        ))

    with st.expander(T("🔬 Why this works")):
        st.markdown(T(
            "- **Retrieval practice:** recalling a phrase builds memory far better than rereading it.\n"
            "- **Spaced repetition:** each phrase comes back after 1, 2, 4, 7, then 15 days.\n"
            "- **Chunks, not single words:** fluent speakers store whole phrases.\n"
            "- **Task-based learning:** role-plays use the phrases for a real goal.\n"
            "- **Interleaving:** daily review mixes phrases from different scenarios."
        ))


# ---------- Moving between lessons ----------

# The course in order: each level's lessons, then its checkpoint
COURSE = [
    step
    for number, level in enumerate(LEVELS, 1)
    for step in [("lesson", sid) for sid in level["scenarios"]]
    + ([("checkpoint", level["checkpoint"]["id"])] if level.get("checkpoint") else [])
]


def step_label(step):
    kind, target = step
    if kind == "lesson":
        scenario = SCENARIO_BY_ID[target]
        return f"{scenario['icon']} {L(scenario, 'title_en')}"
    return T("🏁 Checkpoint {n}", n=CHECKPOINT_BY_ID[target][0])


def goto(step):
    """Button callback: remember where to go; the page follows it on the next run."""
    if step[0] == "lesson":
        st.session_state.scenario = step[1]
    st.session_state["_goto"] = step


def follow_goto(current_page):
    """Switch page if a navigation button asked for another one, and scroll to the top."""
    step = st.session_state.pop("_goto", None)
    if not step:
        return
    st.session_state["_scroll_top"] = True
    kind, target = step
    if kind == "home":
        st.switch_page(PAGES["Home"])
    if kind == "checkpoint":
        st.session_state.checkpoint = target
        if current_page != "Checkpoint":
            st.switch_page(PAGES["Checkpoint"])
    if kind == "lesson" and current_page != "Lesson":
        st.switch_page(PAGES["Lesson"])


def scroll_to_top():
    """After jumping to another lesson, start at the top (the long page keeps its old scroll)."""
    if st.session_state.pop("_scroll_top", False):
        # repeat for ~2 s while the new page draws; the nonce makes Streamlit run a fresh copy
        st.iframe(
            f"<!-- {time.time()} --><script>let n = 0; const top = () => {{"
            "const main = window.parent.document.querySelector('[data-testid=stMain]');"
            "if (main) main.scrollTop = 0; if (++n < 20) setTimeout(top, 100); }; top();</script>",
            height=1,
        )


def glide_to_end(once_key):
    """Smoothly bring the end of the page (e.g. a time-attack summary) into view, once."""
    seen = st.session_state.setdefault("_glided", set())
    if once_key in seen:
        return
    seen.add(once_key)
    st.iframe(
        f"<!-- {once_key} --><script>setTimeout(() => {{"
        "const main = window.parent.document.querySelector('[data-testid=stMain]');"
        "const calm = window.parent.matchMedia('(prefers-reduced-motion: reduce)').matches;"
        "if (main) main.scrollTo({top: main.scrollHeight, behavior: calm ? 'auto' : 'smooth'});"
        "}, 250);</script>",
        height=1,
    )


def course_nav(step, key):
    """← All lessons · ‹ previous · next › bar, with where you are in the course."""
    index = COURSE.index(step)
    previous = COURSE[index - 1] if index > 0 else None
    following = COURSE[index + 1] if index + 1 < len(COURSE) else None
    if step[0] == "lesson":
        number = LEVEL_NUMBER[step[1]]
        lessons = LEVELS[number - 1]["scenarios"]
        where = T("Level {n} · Lesson {i} of {total}", n=number, i=lessons.index(step[1]) + 1, total=len(lessons))
    else:
        where = T("Level {n} · Checkpoint", n=CHECKPOINT_BY_ID[step[1]][0])
    with st.container(key=f"course-nav-{key}"):
        left, middle, right = st.columns([1, 1.4, 1.4], vertical_alignment="center")
        left.button(T("← All lessons"), key=f"{key}-home", on_click=goto, args=(("home", None),),
                    icon=":material/grid_view:")
        if previous:
            middle.button(f"‹ {step_label(previous)}", key=f"{key}-prev", on_click=goto, args=(previous,),
                          width="stretch", help=T("Previous in the course"))
        if following:
            right.button(f"{step_label(following)} ›", key=f"{key}-next", on_click=goto, args=(following,),
                         width="stretch", type="primary", help=T("Next in the course"))
        html(f'<div class="course-where">{where}</div>')


def next_up(step, key):
    """A big 'what's next' button at the end of a lesson."""
    index = COURSE.index(step)
    if index + 1 >= len(COURSE):
        st.success(T("🎉 That's the last lesson for now. More are coming soon!"))
        return
    following = COURSE[index + 1]
    with st.container(border=True, key=f"next-up-{key}"):
        html(f'<div class="prompt-label">{T("Finished this lesson?")}</div>'
             f'<div class="next-title">{escape(T("Next: {label}", label=step_label(following)))}</div>')
        st.button(T("Continue →"), key=f"{key}-continue", on_click=goto, args=(following,), type="primary")


def remembered_tabs(page_id, names):
    """Tabs that stay on the chosen tab when the page redraws.

    Plain st.tabs fall back to the first tab whenever Streamlit rebuilds them (for example the
    first time the time-attack recorder appears), which threw learners back to the dialogue.
    Here the server remembers the tab, per lesson; the labels depend on the language, so the
    memory is the tab's position and each language gets its own widget key."""
    labels = [T(name) for name in names]
    memory = st.session_state.setdefault("lesson-tabs", {})
    key = f"tabs-{page_id}-{lang()}"

    def remember():
        chosen = st.session_state.get(key)
        if chosen in labels:
            memory[page_id] = labels.index(chosen)

    st.session_state[key] = labels[min(memory.get(page_id, 0), len(labels) - 1)]
    return st.tabs(labels, key=key, on_change=remember)


def choose_level():
    """Level switch callback: open that level's first lesson (or stay if it's already there)."""
    number = st.session_state.get(f"lesson-level-{lang()}")
    if number and LEVEL_NUMBER.get(st.session_state.get("scenario")) != number:
        st.session_state.scenario = LEVELS[number - 1]["scenarios"][0]


def lesson_page():
    preload_models()
    follow_goto("Lesson")
    scroll_to_top()
    if st.session_state.get("scenario") not in SCENARIO_BY_ID:  # never trust a stale or odd value
        st.session_state.scenario = SCENARIOS[0]["id"]
    course_nav(("lesson", st.session_state.scenario), "lesson-top")
    # Pick a level first, then one of that level's lessons (folded away: Previous / Next cover most moves).
    # The pickers' labels depend on the language, and Streamlit loses a picker's value when its labels
    # change, so each language gets its own picker; the lesson itself lives in st.session_state.scenario.
    level_key, lesson_key = f"lesson-level-{lang()}", f"lesson-pick-{lang()}"
    st.session_state[level_key] = LEVEL_NUMBER[st.session_state.scenario]
    jump = st.expander(T("🔀 Jump to another lesson"))
    pick_level, pick_lesson = jump.columns([1, 2], vertical_alignment="bottom")
    pick_level.segmented_control(
        T("Level"),
        list(range(1, len(LEVELS) + 1)),
        format_func=lambda n: T("Level {n}", n=n),
        key=level_key,
        on_change=choose_level,
    )
    level_lessons = LEVELS[LEVEL_NUMBER[st.session_state.scenario] - 1]["scenarios"]
    st.session_state[lesson_key] = st.session_state.scenario
    pick_lesson.selectbox(
        T("Lesson"),
        level_lessons,
        format_func=lambda sid: f"{level_lessons.index(sid) + 1}. {SCENARIO_BY_ID[sid]['icon']} "
                                f"{L(SCENARIO_BY_ID[sid], 'title_en')} · {SCENARIO_BY_ID[sid]['title_ko']}",
        key=lesson_key,
        on_change=lambda: st.session_state.update(scenario=st.session_state[lesson_key]),
    )
    scenario_id = st.session_state.scenario
    scenario = SCENARIO_BY_ID[scenario_id]

    html(
        f'<div class="lesson-head"><div class="lesson-icon">{scenario["icon"]}</div><div>'
        f'<span class="pill">{escape(L(scenario, "level"))}</span>'
        f'<span class="pill">{escape(L(scenario, "title_en"))}</span>'
        f'<h1>{escape(scenario["title_ko"])}</h1>'
        f'<p>{escape(L(scenario, "situation_en"))}</p></div></div>'
    )

    situation_tab, notice_tab, recall_tab, roleplay_tab, test_tab = remembered_tabs(
        scenario_id, ["1 · Situation", "2 · Notice", "3 · Recall", "4 · Role-play", "📝 Test"]
    )

    with situation_tab:
        toggles = st.columns(2)
        show_romanization = toggles[0].toggle(T("Show romanization"), value=True)
        show_english = toggles[1].toggle(T("Show English"), value=True)
        if not conversation_player(scenario, show_romanization, show_english):
            for number, line in enumerate(scenario["dialogue"], 1):
                role = "user" if line["speaker"] == "나" else "assistant"
                with st.chat_message(role, avatar=SPEAKER_AVATARS.get(line["speaker"], "🧑")):
                    html(
                        f'<span class="speaker">{escape(line["speaker"])}</span>'
                        f'<span class="ko-line">{escape(line["ko"])}</span>'
                    )
                    if show_romanization:
                        st.caption(line["romanization"])
                    if show_english:
                        st.caption(f"*{L(line, 'en')}*")
                    play(f"{scenario_id}_d{number}")

    with notice_tab:
        for chunk in scenario["chunks"]:
            with st.container(border=True):
                html(
                    f'<div class="ko">{escape(chunk["ko"])}</div>'
                    f'<i>{escape(chunk["romanization"])}</i> '
                    f'<span class="pill accent">{escape(L(chunk, "register"))}</span>'
                    f'<div><b>{escape(L(chunk, "en"))}</b></div>'
                )
                play(chunk["id"])
                html(
                    f'<p class="note">💡 {escape(L(chunk, "note"))}</p>'
                    f'<div class="mistake">⚠️ {escape(L(chunk, "common_mistake"))}</div>'
                )

    with recall_tab:
        icon_steps([("read", T("See the meaning")), ("mic", T("Say it in Korean")), ("calendar", T("It comes back to review"))],
                   more=T("Type or say each phrase in Korean. Every answer goes into your review schedule."))
        recall_session(
            [chunk["id"] for chunk in scenario["chunks"]],
            state_key=f"lesson-{scenario_id}",
            done_message=T("All phrases are in your review queue. Try the role-play next!"),
        )

    with roleplay_tab:
        roleplay(scenario)

    with test_tab:
        test_section(scenario)

    next_up(("lesson", scenario_id), "lesson-bottom")


PRACTICE, TIME_ATTACK = "🗣️ Practice", "⏱️ Time attack"
TIME_ATTACK_COMPONENT = st.components.v2.component(
    "time_attack",
    js=(ASSETS_DIR / "time_attack.js").read_text(encoding="utf-8"),
    css=(ASSETS_DIR / "time_attack.css").read_text(encoding="utf-8"),
)
REACTION_TIME = 1.5  # seconds to start answering
LEARNER_SYLLABLES_PER_SECOND = 2.5  # natives speak ~5-7; learners need about half that pace


def time_limit(accepted):
    """Seconds to answer: reaction time + the shortest good answer at learner pace (3-10 s)."""
    syllables = min(sum("가" <= ch <= "힣" for ch in answer) for answer in accepted)
    return round(min(10.0, max(3.0, REACTION_TIME + syllables / LEARNER_SYLLABLES_PER_SECOND)) * 2) / 2


def pace_note(latency):
    if latency is None:
        return ""
    if latency <= 2.0:
        return T("⚡ Started answering after {seconds} s: natural conversation pace", seconds=f"{latency:.1f}")
    if latency <= 3.5:
        return T("🕐 Started answering after {seconds} s: a little slow, keep practicing", seconds=f"{latency:.1f}")
    return T("🐢 Started answering after {seconds} s: try to answer sooner", seconds=f"{latency:.1f}")


def roleplay(scenario):
    """A new conversation in the same situation: use the phrases for a task.

    Practice: take your time, type or record each reply.
    Time attack: recording starts by itself after their line, and you have a few
    seconds to answer (based on the length of a good answer), like real conversation.
    """
    turns = scenario["roleplay"]
    mode = st.segmented_control(
        T("Mode"), [PRACTICE, TIME_ATTACK], default=PRACTICE, key=f"roleplay-{scenario['id']}-mode",
        format_func=T,
        help=T("Time attack: the recorder starts by itself after their line, and you have a few "
               "seconds to answer, like a real conversation."),
    ) or PRACTICE
    timed = mode == TIME_ATTACK
    answers_key = f"{'timeattack' if timed else 'roleplay'}-{scenario['id']}"
    answers = st.session_state.setdefault(answers_key, [])
    round_ = st.session_state.setdefault(f"{answers_key}-round", 0)
    if timed:
        icon_steps([("read", T("Read the task")), ("listen", T("Listen")), ("timer", T("Answer within seconds"))],
                   more=T("Their line plays, then **you have a few seconds to answer**, no pausing. "
                          "Recording starts and stops by itself. Read the task first!"))
    else:
        icon_steps([("listen", T("Listen")), ("mic", T("Reply in Korean")), ("target", T("Complete the task"))],
                   more=T("A new conversation. Listen to what they say, then reply in Korean to complete the task."))
    listening = st.toggle(
        T("🎧 Listening practice: hide their words until you ask"), key=f"{answers_key}-listening"
    )
    # All lesson tabs load together, so wait for the learner before any voice plays.
    started_key = f"{answers_key}-started"
    if not timed and not st.session_state.get(started_key):
        if st.button(T("▶ Start the conversation"), type="primary", key=f"{answers_key}-start"):
            st.session_state[started_key] = True
            st.rerun()
        return

    finished = len(answers) >= len(turns)
    if timed and finished:  # time attack: a summary instead of scrolling back through the chat
        time_attack_summary(turns, answers, f"{answers_key}-{round_}")
        transcript = st.expander(T("Show the whole conversation"))
    else:
        transcript = st.container()
    for number, (turn, (answer, result, match, ai_note, spoken, *extra)) in enumerate(zip(turns, answers)):
        with transcript, st.chat_message("assistant", avatar="🧑"):
            html(
                f'<span class="speaker">{escape(turn["speaker"])}</span>'
                f'<span class="ko-line">{escape(turn["prompt_ko"])}</span>'
            )
        with transcript, st.chat_message("user", avatar="🙋"):
            st.write(f"🎙️ {answer}" if spoken and answer else (answer or T("⏰ No answer in time")))
            show_feedback(answer, result, match, ai_note, echo=False, accepted=turn["accepted"])
            if extra and extra[0] is not None:
                st.caption(pace_note(extra[0]))
            if spoken:
                my_recording(f"{answers_key}-{round_}-{number}")
                if number == len(answers) - 1:
                    noise_reading()

    if len(answers) < len(turns):
        turn = turns[len(answers)]
        if timed:
            time_attack_turn(scenario, turn, answers, f"{answers_key}-{round_}-{len(answers)}",
                             listening, autostart=bool(answers))
            return
        has_audio = (AUDIO_DIR / f"{turn['id']}.mp3").exists()
        with st.chat_message("assistant", avatar="🧑"):
            if listening and has_audio:
                html(f'<span class="speaker">{escape(turn["speaker"])}</span> {T("🔊 Listen…")}')
                with st.expander(T("Show their words")):
                    st.write(turn["prompt_ko"])
                    st.caption(L(turn, "prompt_en"))
            else:
                html(
                    f'<span class="speaker">{escape(turn["speaker"])}</span>'
                    f'<span class="ko-line">{escape(turn["prompt_ko"])}</span>'
                )
                with st.expander(T("English")):
                    st.write(L(turn, "prompt_en"))
            play(turn["id"], autoplay=True)
        html(f'<div class="task">{T("🎯 <b>Your task:</b> {task}", task=escape(L(turn, "task_en")))}</div>')
        submitted = answer_input(
            f"{answers_key}-{round_}-{len(answers)}", T("Your reply"), hint=scenario_hint(scenario)
        )
        if submitted:
            answer, spoken, hinted = submitted
            result, match, ai_note, answer = grade(
                answer, turn["accepted"], turn.get("keywords", ()), hinted=hinted
            )
            answers.append((answer, result, match, ai_note, spoken))
            st.rerun()
        return

    if not timed:
        passed = sum(result != "wrong" for _, result, *_ in answers)
        st.success(T("Conversation complete: {passed} / {total} replies understood.", passed=passed, total=len(turns)))
    if st.button(T("Try again"), key=f"{answers_key}-again"):
        st.session_state[answers_key] = []
        st.session_state[f"{answers_key}-round"] = round_ + 1
        st.rerun()


RESULT_MARKS = {"exact": ("✅", "Exactly right"), "close": ("⚠️", "Almost: check the spelling"),
                "meaning": ("✅", "Right meaning, different words"), "wrong": ("❌", "Not quite")}


def time_attack_summary(turns, answers, round_key):
    """End of a time-attack round: one compact card with the score and a line per turn
    (your answer, the right one if you missed it, how fast you started). Their lines are in
    "Show the whole conversation"; the recordings in an expander below the card."""
    passed = sum(result != "wrong" for _, result, *_ in answers)
    latencies = [a[5] for a in answers if len(a) > 5 and a[5] is not None]
    natural = sum(latency <= 2.0 for latency in latencies)
    share = passed / len(turns)
    headline = (T("Perfect conversation! 완벽해요!") if passed == len(turns)
                else T("Great conversation!") if share >= 0.7 else T("Good start. Try it again!"))
    rows = []
    for number, (turn, (answer, result, match, ai_note, spoken, *extra)) in enumerate(zip(turns, answers), 1):
        mark = RESULT_MARKS.get(result, RESULT_MARKS["wrong"])[0]
        latency = extra[0] if extra else None
        said = (escape(answer) if answer else T("🔇 (nothing heard)") if latency is not None
                else T("⏰ (no answer)"))
        fix = "" if result in ("exact", "meaning") else f'<div class="ta-fix">→ {escape(match)}</div>'
        rows.append(
            f'<div class="ta-line ta-{result}"><span class="ta-num">{number}</span><span class="ta-mark">{mark}</span>'
            f'<div class="ta-said">{said}{fix}</div>'
            f'<span class="ta-time">{"" if latency is None else f"{latency:.1f}s"}</span></div>'
        )
    pace = (T("average start {seconds} s", seconds=f"{sum(latencies) / len(latencies):.1f}")
            + " · " + T("{n} at natural pace", n=natural)) if latencies else ""
    with st.container(border=True, key=f"ta-summary-{round_key}"):
        html(
            '<div class="ta-score">'
            f'<div class="ta-score-big">{passed}<span>/ {len(turns)}</span></div>'
            f'<div><div class="ta-score-title">{headline}</div><div class="ta-score-sub">{pace}</div></div></div>'
            f'<div class="ta-lines">{"".join(rows)}</div>'
            f'<div class="ta-legend">✅ {T("right")} · ⚠️ {T("almost")} · ❌ {T("missed")} · '
            f'→ {T("a natural answer")} · ⏱️ {T("time to start speaking")}</div>'
        )
    recorded = [(number, f"{round_key}-{number - 1}") for number, answer in enumerate(answers, 1)
                if st.session_state.get("recordings", {}).get(f"{round_key}-{number - 1}")]
    if recorded:
        with st.expander(T("🎙️ Listen to your answers")):
            for number, key in recorded:
                st.caption(f"{number}. {T('You')}")
                kept = st.session_state["recordings"][key]
                st.audio(kept[0], format=kept[1])
    glide_to(f"st-key-ta-summary-{round_key}", round_key)


def glide_to(css_class, once_key):
    """Smoothly bring an element (by its st-key-… class) to the top of the view, once."""
    seen = st.session_state.setdefault("_glided", set())
    if once_key in seen:
        return
    seen.add(once_key)
    st.iframe(
        f"<!-- {once_key} --><script>const glide = (smooth) => {{"
        "const doc = window.parent.document;"
        f"const target = doc.querySelector('.{css_class}');"
        "const main = doc.querySelector('[data-testid=stMain]');"
        "if (!target || !main) return;"
        "const calm = window.parent.matchMedia('(prefers-reduced-motion: reduce)').matches || doc.hidden;"
        "const top = main.scrollTop + target.getBoundingClientRect().top - main.getBoundingClientRect().top - 84;"
        "if (Math.abs(main.scrollTop - top) > 40) main.scrollTo({top: Math.max(0, top), behavior: smooth && !calm ? 'smooth' : 'auto'});"
        "}; setTimeout(() => glide(true), 300); setTimeout(() => glide(false), 1500);</script>",
        height=1,
    )


def time_attack_turn(scenario, turn, answers, turn_id, listening, autostart):
    """One timed turn: their line plays, the recorder starts by itself, answer in time."""
    limit = time_limit(turn["accepted"])
    with st.chat_message("assistant", avatar="🧑"):
        if listening:
            html(f'<span class="speaker">{escape(turn["speaker"])}</span> {T("🔊 Listen…")}')
        else:
            html(
                f'<span class="speaker">{escape(turn["speaker"])}</span>'
                f'<span class="ko-line">{escape(turn["prompt_ko"])}</span>'
            )
    path = AUDIO_DIR / f"{turn['id']}.mp3"
    result = TIME_ATTACK_COMPONENT(
        key=f"ta-{turn_id}",
        data={
            "turn_id": turn_id,
            "audio": ("data:audio/mpeg;base64," + base64.b64encode(path.read_bytes()).decode())
            if path.exists() else "",
            "limit": limit,
            "speaker": turn["speaker"],
            "task": L(turn, "task_en"),
            "listen_text": T("Listen…") if listening else turn["prompt_ko"],
            "labels": {text: T(text) for text in (
                "Answer sent. Checking…", "Microphone blocked. Allow it in the browser and try again.",
                "Your turn: speak now!", "Got it. Checking…", "Time's up!",
                "Press start. Their line plays, then you have to answer in time.")},
            "limit_text": T("{seconds} s to answer", seconds=f"{limit:.1f}"),
            "dark": st.context.theme.type == "dark",
            "autostart": autostart,  # the first turn needs a click (browsers require it for sound)
        },
        on_answer_change=lambda: None,
    )
    reply = getattr(result, "answer", None)
    done = st.session_state.setdefault("time-attack-done", set())
    if not reply or reply.get("turn_id") != turn_id or turn_id in done:
        return
    done.add(turn_id)
    if not reply.get("spoke"):
        answers.append(("", "wrong", turn["accepted"][0], T("⏰ Time's up: no answer heard"), asr_engine(), None))
        st.rerun()
    audio = base64.b64decode(reply["audio"])
    keep_recording(turn_id, audio, reply.get("mime") or "audio/webm")
    speech_model()
    with st.spinner(T("Listening…")):
        plain = transcribe(audio)
    note_surroundings(audio, popup="toast")  # time attack: no popup over the next turn's recorder
    if not plain:
        answers.append(("", "wrong", turn["accepted"][0], T("No words recognized"), asr_engine(), reply.get("latency")))
        st.rerun()
    hint = scenario_hint(scenario)
    result, match, ai_note, answer = grade(
        plain, turn["accepted"], turn.get("keywords", ()), hinted=lambda: transcribe(audio, hint=hint)
    )
    answers.append((answer, result, match, ai_note, asr_engine(), reply.get("latency")))
    st.rerun()


TEST_TITLES = {"pre": "Pre-test", "post": "Post-test", "checkpoint": "Checkpoint test"}


def start_test(test_id, kind, items):
    round_ = st.session_state.get(f"test-round-{test_id}", 0)
    st.session_state[f"test-round-{test_id}"] = round_ + 1
    st.session_state[f"test-{test_id}"] = {"kind": kind, "items": items, "answers": [], "round": round_}
    st.rerun()


def run_test(test_id, hint):
    """Show the running test (one phrase at a time, no feedback). Returns True while running."""
    running = st.session_state.get(f"test-{test_id}")
    if not running:
        return False
    items, answers = running["items"], running["answers"]
    title = T(TEST_TITLES[running["kind"]])
    if len(answers) < len(items):
        chunk = CHUNK_BY_ID[items[len(answers)]][0]
        st.progress(len(answers) / len(items), text=f"{title}: {len(answers) + 1} / {len(items)}")
        html(f'<div class="prompt-label">{T("How do you say it in Korean?")}</div>'
             f'<div class="prompt-en">{escape(L(chunk, "en"))}</div>')
        key = f"test-{test_id}-{running['round']}-{len(answers)}"
        submitted = answer_input(key, T("Your answer"), hint=hint)
        columns = st.columns(2)
        if columns[0].button(T("I don't know yet →"), key=f"{key}-skip"):
            answers.append({"chunk": chunk["id"], "answer": "", "result": "wrong"})
            st.rerun()
        if columns[1].button(T("Stop the test"), key=f"{key}-stop"):
            del st.session_state[f"test-{test_id}"]
            st.rerun()
        if submitted:
            answer, _, hinted = submitted
            accepted = [chunk["ko"], *chunk.get("alternatives", [])]
            result, _, _, answer = grade(answer, accepted, hinted=hinted)
            answers.append({"chunk": chunk["id"], "answer": answer, "result": result})
            st.rerun()
        return True
    tests = load_tests()
    result = learning_tests.record(tests, test_id, running["kind"], answers)
    save_tests(tests)
    del st.session_state[f"test-{test_id}"]
    st.session_state[f"test-done-{test_id}"] = (title, result["correct"], result["total"])
    st.rerun()


def show_test_answers(result, label="Answers from your last test"):
    with st.expander(f"{T(label)} ({result['date']})"):
        for item in result["answers"]:
            chunk = CHUNK_BY_ID.get(item["chunk"], ({}, None))[0]
            mark = "✅" if item["result"] in learning_tests.COUNTS_AS_KNOWN else "❌"
            also = " · ".join(chunk.get("alternatives", []))
            st.markdown(f"{mark} **{escape(L(chunk, 'en') if chunk else '')}** → {escape(chunk.get('ko', ''))}  \n"
                        + (f"<small>{T('Also correct: {also}', also=escape(also))}</small>  \n" if also else "")
                        + f"<small>{T('You: {answer}', answer=escape(item['answer'] or T('(no answer)')))}</small>",
                        unsafe_allow_html=True)


def test_section(scenario):
    """Pre-test before the lesson, post-test after: measures what the lesson taught."""
    if run_test(scenario["id"], scenario_hint(scenario)):
        return
    tests = load_tests()
    entry = tests.get(scenario["id"]) or {}
    pre, post, gain = learning_tests.summary(tests, scenario["id"])
    if done := st.session_state.pop(f"test-done-{scenario['id']}", None):
        st.success(T("{title} finished: {correct} / {total} phrases known.", title=done[0], correct=done[1], total=done[2]))
    icon_steps([("test", T("Pre-test")), ("study", T("Study")), ("test", T("Post-test")), ("chart", T("See your gain"))],
               more=T("Measure what this lesson teaches you. Take the **pre-test before** you start (it's fine to know nothing "
                      "yet!) and the **post-test after** studying. Each test asks every phrase from its English meaning, with no "
                      "hints. You see the answers at the end. Tests don't change your review schedule."))
    columns = st.columns(3)
    columns[0].metric(T("Pre-test"), "–" if pre is None else f"{pre:.0%}")
    columns[1].metric(T("Post-test"), "–" if post is None else f"{post:.0%}")
    columns[2].metric(T("Gain"), "–" if gain is None else f"{gain:+.0%}")
    kind = "pre" if entry.get("pre") is None else "post"
    if kind == "pre":
        label = T("📝 Start the pre-test")
    else:
        label = T("📝 Take the post-test again") if entry.get("post") else T("📝 Take the post-test")
        st.caption(T("Pre-test done. Study the lesson (Situation → Role-play), then take the post-test."))
    if st.button(label, type="primary", key=f"test-start-{scenario['id']}"):
        start_test(scenario["id"], kind, learning_tests.test_items(scenario, kind))
    last = (entry.get("post") or [None])[-1] or entry.get("pre")
    if last:
        show_test_answers(last)


def checkpoint_page():
    """A level's checkpoint: a mixed test (pass 80%) and a story role-play across the level."""
    preload_models()
    follow_goto("Checkpoint")
    scroll_to_top()
    checkpoint_id = st.session_state.get("checkpoint") or next(iter(CHECKPOINT_BY_ID))
    course_nav(("checkpoint", checkpoint_id), "checkpoint-top")
    number, level = CHECKPOINT_BY_ID[checkpoint_id]
    checkpoint = level["checkpoint"]
    scenarios = [SCENARIO_BY_ID[sid] for sid in level["scenarios"]]
    items = learning_tests.checkpoint_items(checkpoint, scenarios)
    html(
        f'<div class="lesson-head"><div class="lesson-icon">{checkpoint.get("icon", "🏁")}</div><div>'
        f'<span class="pill">{escape(T("Level {n} · {title}", n=number, title=L(level, "title_en")))}</span>'
        f'<span class="pill accent">{T("pass: {pct}", pct=f"{checkpoint.get("pass", 0.8):.0%}")}</span>'
        f'<h1>{escape(checkpoint["title_ko"])}</h1>'
        f'<p>{escape(L(checkpoint, "title_en"))}{T(". ")}{escape(L(checkpoint, "situation_en"))}</p></div></div>'
    )
    test_tab, story_tab = remembered_tabs(checkpoint_id, [T("📝 Mixed test ({n} phrases)", n=len(items)),
                                                         T("🗣️ Story role-play ({n} turns)", n=len(checkpoint['roleplay']))])
    with test_tab:
        test_pool = {"id": checkpoint_id, "chunks": [CHUNK_BY_ID[i][0] for i in items]}
        if run_test(checkpoint_id, scenario_hint(test_pool)):
            return
        tests = load_tests()
        best, latest, passed = learning_tests.checkpoint_status(tests, checkpoint)
        if done := st.session_state.pop(f"test-done-{checkpoint_id}", None):
            score = done[1] / done[2]
            if score >= checkpoint.get("pass", 0.8):
                st.success(T("🎉 {correct} / {total} ({pct}): Level {n} complete!", correct=done[1], total=done[2],
                             pct=f"{score:.0%}", n=number)
                           + (T(" Level {n} is unlocked.", n=number + 1) if number < len(LEVELS) else ""))
                st.balloons()
            else:
                last = tests[checkpoint_id]["checkpoint"][-1]
                missed = {CHUNK_BY_ID[a["chunk"]][1]["id"] for a in last["answers"]
                          if a["result"] not in learning_tests.COUNTS_AS_KNOWN}
                names = ", ".join(f"{SCENARIO_BY_ID[s]['icon']} {L(SCENARIO_BY_ID[s], 'title_en')}"
                                  for s in level["scenarios"] if s in missed)
                st.warning(T("Not yet: {correct} / {total} ({pct}). You need {need}. Review: {names}, then try again.",
                             correct=done[1], total=done[2], pct=f"{score:.0%}",
                             need=f"{checkpoint.get('pass', 0.8):.0%}", names=names))
        pass_pct = f"{checkpoint.get('pass', 0.8):.0%}"
        icon_steps([("test", T("{n} phrases", n=len(items))), ("shuffle", T("Mixed")), ("nohint", T("No hints")),
                    ("target", T("{pct} to pass", pct=pass_pct))],
                   more=T("{n} phrases, {per} from each Level {level} lesson, mixed together. No hints and no feedback until the "
                          "end, just like a lesson test. Score {pct} or more to complete the level. You can take it anytime, even "
                          "before the lessons, to see if you can skip ahead.",
                          n=len(items), per=checkpoint.get('test_per_scenario', 2), level=number, pct=pass_pct))
        columns = st.columns(3)
        columns[0].metric(T("Best score"), "–" if best is None else f"{best:.0%}")
        columns[1].metric(T("Last attempt"), "–" if latest is None else f"{latest:.0%}")
        columns[2].metric(T("Status"), T("✅ Passed") if passed else T("Not yet"))
        if st.button(T("📝 Start the checkpoint test"), type="primary", key=f"start-{checkpoint_id}"):
            start_test(checkpoint_id, "checkpoint", items)
        if (tests.get(checkpoint_id) or {}).get("checkpoint"):
            show_test_answers(tests[checkpoint_id]["checkpoint"][-1], "Answers from your last attempt")
    with story_tab:
        icon_steps([("roleplay", T("One turn per lesson")), ("repeat", T("Practice, not scored"))],
                   more=T("One turn from each part of the level, in a row, like a real day out. Practice it here; the story isn't "
                          "scored for passing."))
        story = {"id": checkpoint_id, "roleplay": checkpoint["roleplay"],
                 "chunks": [chunk for scenario in scenarios for chunk in scenario["chunks"]]}
        roleplay(story)


def review_page():
    preload_models()
    st.title(T("🔁 Review"))
    if not progress():
        st.info(T("Nothing to review yet. Start a lesson first!"))
        if st.button(T("Go to lessons")):
            go("Lesson")
        return

    if "review-queue" not in st.session_state:
        queue = srs.due_items(progress())
        random.shuffle(queue)  # interleave scenarios
        st.session_state["review-queue"] = queue
    queue = st.session_state["review-queue"]

    if not queue:
        st.success(T("Nothing due today. Come back tomorrow! 🎉"))
    else:
        st.write(T("{n} phrases due, mixed from all scenarios.", n=len(queue)))
        recall_session(
            queue,
            state_key="review",
            done_message=T("Review finished for today. 수고했어요!"),
        )

    if st.button(T("Refresh due phrases")):
        st.session_state.pop("review-queue")
        st.session_state["review-index"] = 0
        st.session_state["review-round"] = st.session_state.get("review-round", 0) + 1
        st.rerun()


def learning_gains():
    """Pre-test → post-test per scenario."""
    tests = load_tests()
    rows = []
    for scenario in SCENARIOS:
        pre, post, gain = learning_tests.summary(tests, scenario["id"])
        if pre is not None:
            rows.append({
                T("Scenario"): f"{scenario['icon']} {L(scenario, 'title_en')}",
                T("Pre-test"): f"{pre:.0%}",
                T("Post-test"): "–" if post is None else f"{post:.0%}",
                T("Gain"): "–" if gain is None else f"{gain:+.0%}",
            })
    for checkpoint_id, (number, level) in CHECKPOINT_BY_ID.items():
        best, latest, passed = learning_tests.checkpoint_status(tests, level["checkpoint"])
        if best is not None:
            rows.append({T("Scenario"): T("🏁 Checkpoint {n} (Level {n})", n=number), T("Pre-test"): "",
                         T("Post-test"): T("best {pct}", pct=f"{best:.0%}"),
                         T("Gain"): T("✅ passed") if passed else T("not yet")})
    st.subheader(T("Learning gains"))
    if not rows:
        st.caption(T("Take a lesson's 📝 Test before and after studying to see what it taught you."))
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True)


def progress_page():
    st.title(T("📈 Progress"))
    learning_gains()
    items = progress()
    if not items:
        st.info(T("No progress yet. Finish a lesson to see your stats."))
        return

    today = date.today().isoformat()
    history = [
        (chunk_id, entry["correct"])
        for chunk_id, item in items.items()
        for entry in item["history"]
    ]
    accuracy = sum(correct for _, correct in history) / len(history) if history else 0

    metrics = st.columns(4)
    metrics[0].metric(T("Phrases learned"), len(items))
    metrics[1].metric(T("Due today"), sum(item["due"] <= today for item in items.values()))
    metrics[2].metric(T("Mastered (box 5)"), sum(item["box"] == srs.MAX_BOX for item in items.values()))
    metrics[3].metric(T("Recall accuracy"), f"{accuracy:.0%}")

    st.subheader(T("Recall accuracy over time"))
    daily = pd.DataFrame(
        [{"date": entry["date"], "correct": entry["correct"]}
         for item in items.values() for entry in item["history"]]
    )
    if daily["date"].nunique() < 2:
        st.caption(T("Practice on two or more days to see a trend. Each point is one day's share of correct answers in "
                     "Recall and Review."))
    else:
        by_day = daily.groupby("date")["correct"].agg(["mean", "count"]).reset_index()
        st.line_chart(
            by_day.assign(**{T("Accuracy (%)"): by_day["mean"] * 100}).set_index("date")[[T("Accuracy (%)")]],
            y_label=T("% correct"),
        )
        st.caption(T("{days} days, {answers} answers. Spaced repetition brings back harder phrases more often, so a flat line "
                     "can still mean progress.", days=len(by_day), answers=int(by_day['count'].sum())))

    st.subheader(T("Phrases per box"))
    st.caption(T("Box 1 comes back tomorrow; box 5 waits 15 days."))
    boxes = pd.Series([item["box"] for item in items.values()]).value_counts()
    st.bar_chart(
        pd.DataFrame(
            {T("Phrases"): [int(boxes.get(box, 0)) for box in srs.INTERVALS]},
            index=[T("Box {box} ({days}d)", box=box, days=days) for box, days in srs.INTERVALS.items()],
        )
    )

    st.subheader(T("Accuracy by scenario"))
    rows = []
    for scenario in SCENARIOS:
        results = [
            correct
            for chunk_id, correct in history
            if CHUNK_BY_ID.get(chunk_id, (None, {}))[1].get("id") == scenario["id"]
        ]
        if results:
            rows.append(
                {T("Scenario"): L(scenario, "title_en"), T("Answers"): len(results),
                 T("Accuracy"): f"{sum(results) / len(results):.0%}"}
            )
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    with st.expander(T("All phrases")):
        st.dataframe(
            pd.DataFrame(
                [
                    {T("Phrase"): CHUNK_BY_ID[chunk_id][0]["ko"], T("Box"): item["box"], T("Next review"): item["due"]}
                    for chunk_id, item in items.items()
                    if chunk_id in CHUNK_BY_ID
                ]
            ),
            hide_index=True,
        )

    with st.expander(T("Reset progress")):
        if st.button(T("Delete all progress"), type="secondary"):
            st.session_state.progress = {}
            save_progress()
            st.rerun()


def team_password():
    """One password for the team-only parts online (survey results, Model lab): the
    TEAM_PASSWORD secret on Hugging Face (SURVEY_PASSWORD also works), or team_password in
    .streamlit/secrets.toml. Without one, those parts stay locked online."""
    for name in ("TEAM_PASSWORD", "SURVEY_PASSWORD"):
        if os.environ.get(name):
            return os.environ[name]
    try:
        return next((st.secrets[k] for k in ("TEAM_PASSWORD", "team_password", "SURVEY_PASSWORD", "survey_password") if k in st.secrets), None)
    except Exception:
        return None


def team_unlocked(what="the survey results", expanded=False):
    """Locally (or for signed-in team members) always open; online, ask for the team password.
    Entering it once unlocks every team-only part for this visit."""
    if is_admin() or st.session_state.get("team-unlocked"):
        return True
    password = team_password()
    if not password:
        st.caption(T("🔒 This part is for the project team."))
        return False
    failed = st.session_state.get("team-password-failed", False)
    with st.expander(T("🔒 Team: see {what}", what=T(what)), expanded=expanded or failed):
        if failed:
            st.error(T("That's not the password."))
        with st.form("survey-password"):
            attempt = st.text_input(T("Password"), type="password")
            if st.form_submit_button(T("Unlock")):
                ok = hmac.compare_digest(attempt.encode(), password.encode())
                st.session_state["team-unlocked"] = ok
                st.session_state["team-password-failed"] = not ok
                st.rerun()
    return False


def feedback_page():
    """Anonymous survey for classmates: usability (SUS) and learning."""
    st.title(T("💬 Feedback"))
    if st.session_state.pop("feedback-sent", False):
        st.success(T("Thank you! Your answers were saved. 감사합니다! 🙏"))
    st.write(T(
        "Tried a lesson or two? Please tell us what you think. It takes about 2 minutes, it's anonymous, and it "
        "helps us improve the app."
    ))
    with st.form("feedback", clear_on_submit=True):
        level = st.radio(T("Your Korean level"), survey.LEVELS, horizontal=True, index=None, format_func=T)
        st.markdown(T("**Using the app** (1 = strongly disagree, 5 = strongly agree)"))
        sus = [
            st.radio(f"{number}. {T(question)}", list(survey.SCALE), index=None, horizontal=True,
                     format_func=str, key=f"sus-{number}")
            for number, question in enumerate(survey.SUS_QUESTIONS, 1)
        ]
        st.markdown(T("**Learning**"))
        learning = [
            st.radio(T(question), list(survey.SCALE), index=None, horizontal=True, format_func=str,
                     key=f"learn-{number}")
            for number, question in enumerate(survey.LEARNING_QUESTIONS, 1)
        ]
        useful = st.text_area(T("What was most useful?"))
        improve = st.text_area(T("What should we improve or add?"))
        sent = st.form_submit_button(T("Send feedback"), type="primary")
    if sent:
        if None in sus or None in learning:
            st.error(T("Please answer every 1-5 question (the open questions are optional)."))
        else:
            survey.add(level, sus, learning, useful, improve)
            st.session_state["feedback-sent"] = True
            st.rerun()

    responses = survey.load()
    results = survey.summary(responses)
    if not team_unlocked("the survey results"):
        return
    with st.expander(f"📊 Results so far ({len(responses)} responses)"):
        if not results:
            st.caption("No responses yet.")
            return
        st.metric("Average SUS score", f"{results['sus']:.0f} / 100",
                  help="System Usability Scale: 68 is average, above 80 is excellent.")
        st.caption(f"That is **{survey.sus_grade(results['sus'])}**. 68 is the average across many "
                   "studies; above 80 is in the top 10%.")
        st.dataframe(
            pd.DataFrame({"Question": survey.LEARNING_QUESTIONS,
                          "Average (1-5)": [round(v, 1) for v in results["learning"]]}),
            hide_index=True,
        )
        for response in responses[::-1]:
            notes = [f"👍 {response['most_useful']}" if response["most_useful"] else "",
                     f"🔧 {response['improve']}" if response["improve"] else ""]
            if any(notes):
                st.caption(f"{response['date']} · {response['level'] or 'level not given'}: "
                           + "  ".join(n for n in notes if n))


@st.cache_resource(show_spinner=False)
def cafe_music():
    """Background music with lyrics (from coach/music.py) for the Model lab demo."""
    from coach import music as evaluate_music

    return evaluate_music.make_music()


def mix_with_music(clip, voice_db):
    from coach import music as evaluate_music

    return evaluate_music.in_cafe(clip, cafe_music(), voice_db)


def model_lab_page():
    """Showcase: the same recording through each speech model, side by side."""
    st.title("🔬 Model lab")
    st.write(
        "Speech recognition turns your Korean into text before the app checks it. Try the same "
        "recording with different AI models and see what each one hears, how fast it is, and "
        "whether your answer would pass."
    )
    if not team_unlocked("the Model lab", expanded=True):
        return
    engines = speech.available_engines()
    if len(engines) == 1:
        st.info(f"This online version runs **{speech.ENGINES[engines[0]]['label']}** only, to fit the "
                "free server. Try how it copes with your voice and café music below, and see how the "
                "other models did in our tests at the bottom of the page. To compare them all live, "
                "run the app on a laptop.", icon="ℹ️")
    phrases = [(chunk, scenario) for scenario in SCENARIOS for chunk in scenario["chunks"]]
    labels = {chunk["id"]: f"{scenario['icon']} {chunk['ko']} · {chunk['en']}" for chunk, scenario in phrases}

    st.subheader("1. Choose a recording")
    source = st.segmented_control("Recording", ["🔊 Sample phrase", "🎙️ My voice"],
                                  default="🔊 Sample phrase", key="lab-source") or "🔊 Sample phrase"
    target_id = st.selectbox(
        "Phrase" if source.startswith("🔊") else "Which phrase are you saying?",
        [chunk["id"] for chunk, _ in phrases], format_func=labels.get, key="lab-phrase",
    )
    chunk, scenario = CHUNK_BY_ID[target_id]
    audio = None
    if source.startswith("🔊"):
        audio = em_decode(AUDIO_DIR / f"{target_id}.mp3")
    else:
        recording = st.audio_input("Say the phrase", key="lab-recording")
        if recording:
            audio = speech.to_array(recording.getvalue())
    noise = st.segmented_control(
        "Background", ["Quiet", "Café music, quieter than you", "Café music, as loud as you"],
        default="Quiet", key="lab-noise", help="Music with sung lyrics, from our noise tests.",
    ) or "Quiet"
    if audio is not None and noise != "Quiet":
        audio = mix_with_music(audio, 5 if "quieter" in noise else 0)
    if audio is not None:
        buffer = io.BytesIO()
        speech.write_wav(buffer, audio)
        st.audio(buffer.getvalue(), format="audio/wav")

    st.subheader("2. Choose models")
    chosen = st.multiselect(
        "Models", engines, default=[e for e in engines if e != "whisper-turbo"],
        format_func=lambda e: f"{speech.ENGINES[e]['label']} · {speech.ENGINES[e]['tag']}", key="lab-models",
    )
    if "whisper-turbo" in chosen:
        st.warning("Whisper turbo is very slow without a graphics card: expect about a minute on the "
                   "free server. It's quicker on a laptop.")
    run = st.button("▶ Compare", type="primary", disabled=audio is None or not chosen, key="lab-run")
    if run:
        accepted = [chunk["ko"], *chunk.get("alternatives", [])]
        hint = scenario_hint(scenario)
        results = []
        for engine in chosen:
            speech_model(engine)
            with st.spinner(f"{speech.ENGINES[engine]['label']} is listening…"):
                start = time.time()
                plain = speech.transcribe({"raw": audio, "sampling_rate": speech.SR}, engine=engine)
                seconds = time.time() - start
                verdict, _, _, heard, how = check_spoken(
                    plain, accepted, (),
                    lambda e=engine: speech.transcribe({"raw": audio, "sampling_rate": speech.SR}, hint=hint, engine=e),
                ) if plain else ("wrong", None, 0, "", "")
            results.append({"engine": engine, "plain": plain, "heard": heard, "how": how,
                            "verdict": verdict, "seconds": seconds})
        st.session_state["lab-results"] = {"target": target_id, "results": results}

    lab = st.session_state.get("lab-results")
    if lab and lab["target"] == target_id:
        st.subheader("3. What each model heard")
        columns = st.columns(len(lab["results"]))
        for column, result in zip(columns, lab["results"]):
            with column.container(border=True):
                info = speech.ENGINES[result["engine"]]
                st.markdown(f"**{info['label']}**  \n<small>{info['tag']}</small>", unsafe_allow_html=True)
                html(f'<div class="ko-line">{escape(result["plain"] or "(heard nothing)")}</div>')
                st.caption(f"⏱️ {result['seconds']:.1f} s")
                if result["verdict"] in ("exact", "close"):
                    st.success("Answer passes" + (" (after a second, closer listen)" if result["how"] == "hint" else ""))
                else:
                    st.error("Answer doesn't pass")
                engine_card(result["engine"], compact=True)
        st.caption(f"Target phrase: {chunk['ko']}. The check is the app's real one: spelling, numbers "
                   "and key words, and a careful second listen with the lesson's phrases as a hint.")

    st.subheader("Benchmark: every model on the app's tests")
    rows = []
    for engine, info in speech.ENGINES.items():
        path = DATA_DIR / "asr_comparison" / f"{engine}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "Model": f"{info['label']} ({info['tag']})",
            "Clean phrases": f"{data['clean']['passed']} / {data['clean']['total']}",
            "Music, quieter than voice": f"{data['music']['5 dB']['right_accepted']} / 28",
            "Music, as loud as voice": f"{data['music']['0 dB']['right_accepted']} / 28",
            "Wrong answers accepted": sum(v["wrong_accepted"] for v in data["music"].values()),
            "Accepted from silence": sum(v["accepted"] for v in data["no_speech"].values()),
            "Seconds per answer (2 CPU cores)": data.get("speed", {}).get("seconds_per_answer"),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.caption("Same audio for every model, graded with the app's real checks. Speed measured on 2 CPU "
                   "cores like the free Hugging Face server. Details: dev/compare_asr.py and the README.")


def em_decode(path):
    """Decode an audio file to 16 kHz floats."""
    return speech.to_array(str(path))


# ---------- Layout ----------

st.set_page_config(page_title="Scenario Vocab Coach", page_icon="🇰🇷", layout="wide")
html(f"<style>{STYLE_PATH.read_text(encoding='utf-8')}</style>")
if st.context.theme.type == "light":
    html(f"<style>{LIGHT_STYLE_PATH.read_text(encoding='utf-8')}</style>")

STORAGE_NOTES = {  # (text, tooltip)
    "browser": ("💾 Your progress is saved only in this browser, on this device",
                "Your progress is stored in this browser's local storage. It stays when you refresh or come back later, "
                "but not on another device or browser, and clearing browser data deletes it."),
    "server": ("💾 Progress resets when the app restarts",
               "Your progress is kept only on this server and is erased whenever the app restarts (after updates or "
               "long inactivity)."),
    "local": ("💾 Progress is saved on this computer", "Saved in data/ on this computer."),
}
_note, _tip = STORAGE_NOTES[storage_mode()]
RESET_NOTE = f'<span title="{escape(T(_tip))}">{T(_note)}</span>'

if login_enabled() and not st.user.is_logged_in:
    # Deployed: nobody gets past this screen without signing in with Google.
    html(
        '<div class="hero" style="margin-top:2rem">'
        '<div class="hero-kicker">부산에서 바로 쓰는 한국어 · REAL KOREAN FOR BUSAN</div>'
        "<h1>Scenario Vocab <span class=\"accent-word\">Coach</span></h1>"
        "<p>Learn the Korean you actually need in Busan: whole phrases inside real situations. "
        "Sign in with your Google account to keep your own progress.</p></div>"
    )
    if st.button("Sign in with Google", type="primary", icon=":material/login:"):
        st.login("google")
    st.caption("We only use your Google account to tell learners apart. Your email is never shown "
               "to anyone, and progress is stored under an anonymous ID.")
    html(f'<div class="wip-banner">{RESET_NOTE}</div>')
    st.stop()

PAGES = {
    "Home": st.Page(home_page, title=T("Home"), icon="🏠", url_path="home", default=True),
    "Lesson": st.Page(lesson_page, title=T("Lesson"), icon="📖", url_path="lesson"),
    "Review": st.Page(review_page, title=T("Review"), icon="🔁", url_path="review"),
    "Progress": st.Page(progress_page, title=T("Progress"), icon="📈", url_path="progress"),
    "Feedback": st.Page(feedback_page, title=T("Feedback"), icon="💬", url_path="feedback"),
    "Model lab": st.Page(model_lab_page, title="Model lab", icon="🔬", url_path="model-lab"),
    "Checkpoint": st.Page(checkpoint_page, title=T("Checkpoint"), icon="🏁", url_path="checkpoint",
                          visibility="hidden"),
}
if dev_mode():
    PAGES["Voice check"] = st.Page(voice_check_page, title="Voice check" + DEV_MARK, icon="🎧",
                                   url_path="voice-check")
navigation = st.navigation(list(PAGES.values()), position="top")
load_from_browser()  # browser mode: this browser's saved progress, before any page reads it

def choose_language():
    if st.session_state.lang is None:  # clicked the chosen language again: keep it
        st.session_state.lang = st.query_params.get("lang", "en")
    st.query_params["lang"] = st.session_state.lang


# keep ?lang=ja in the address, so a refresh or a shared link stays in Japanese
if lang() == "ja" or "lang" in st.query_params:
    st.query_params["lang"] = lang()

with st.sidebar:
    st.segmented_control(T("🌐 Language"), list(LANGUAGES), format_func=LANGUAGES.get, key="lang",
                         on_change=choose_language, label_visibility="collapsed")
    items = progress()
    due_today = len(srs.due_items(items))
    mastered = sum(item["box"] == srs.MAX_BOX for item in items.values())
    html(
        '<div class="side-brand">'
        '<div class="side-logo">🇰🇷</div>'
        '<div class="brand">Vocab <span>Coach</span></div>'
        f'<div class="brand-sub">부산 생활 한국어 · {T("Korean for life in Busan")}</div>'
        f'<span class="wip-badge">{T("🚧 Under construction")}</span>'
        "</div>"
        '<div class="side-stats">'
        f'<a class="stat due" href="review" target="_self" title="{escape(T("Phrases your review schedule brings back today. Each correct answer pushes a phrase further away (1, 2, 4, 7, then 15 days); a wrong one brings it back tomorrow. Click to review."))}">'
        f'<b>{due_today}</b><span>{T("to review")}</span></a>'
        f'<div class="stat" title="{escape(T("Phrases you have practiced at least once"))}"><b>{len(items)}</b>'
        f'<span>{T("learned")}</span></div>'
        f'<div class="stat" title="{escape(T("Phrases in the last box: you got them right 4 times in a row, spread over weeks"))}">'
        f'<b>{mastered}</b><span>{T("mastered")}</span></div>'
        "</div>"
        f'<div class="side-label">{T("Practice settings")}</div>'
    )
    with st.container(border=True, key="side-settings"):
        st.segmented_control(
            T("Answer by"),
            [SPEAK, TYPE] if speech.is_available() else [TYPE],
            default=SPEAK if speech.is_available() else TYPE,
            key="answer_mode",
            format_func=T,
            help=T("Speak uses the microphone and a speech-recognition model, chosen below."),
        )
        engines = speech.available_engines()
        if len(engines) > 1:
            st.selectbox(
                T("Speech model"),
                engines,
                index=engines.index(speech.DEFAULT_ENGINE),
                format_func=lambda e: f"{speech.ENGINES[e]['label']} · {speech.ENGINES[e]['tag']}",
                key="asr_engine",
                help=T("Compare them side by side on the 🔬 Model lab page."),
            )
            with st.expander(T("About this model")):
                engine_card(asr_engine(), compact=True)
        st.toggle(
            T("🤖 AI meaning check"),
            value=semantic.is_available(),
            disabled=not semantic.is_available(),
            key="ai_check",
            help=T("Accept answers with different words but the same meaning (Hugging Face model {model}).",
                   model=semantic.MODEL_NAME),
        )
    if login_enabled():
        st.caption(T("Signed in as **{name}**", name=st.user.get('name') or user_email()))
        if st.button(T("Sign out"), icon=":material/logout:", key="sign-out"):
            st.logout()
    html(
        f'<div class="side-foot">{T("Made at BUFS for international students in Busan")}<br>'
        f'{T("AI project prototype · v0.1")}</div>'
    )

html(
    f'<div class="wip-banner"><span title="{escape(T("The Korean content and voices are still being checked, so expect rough edges."))}">'
    f'{T("🚧 Class prototype, still being checked")}</span>'
    + (f'<span class="wip-sep">·</span><span>{T("🇯🇵 Japanese is AI-translated, still being checked")}</span>'
       if lang() == "ja" else "")
    + f'<span class="wip-sep">·</span>{RESET_NOTE}</div>'
)

noise_banner()
navigation.run()
save_to_browser()  # browser mode: write any changes back to this browser
