// Time-attack role-play turn (a Streamlit v2 component, mounted by app.py).
//
// Plays the other person's line, then starts recording by itself and gives the
// learner a few seconds to answer, like a real conversation. Recording stops
// when the learner goes quiet after speaking, or when time runs out. The
// recording (webm/opus, base64) goes back to Python with how fast they started.

const SPEECH_LEVEL = 0.02;   // RMS above this counts as speaking
const END_SILENCE = 0.9;     // seconds of quiet after speech that end the answer
const MIN_SPEECH = 0.25;     // seconds of speech needed before quiet can end it

// One microphone stream for the whole page, so the browser asks only once.
const shared = (window.__timeAttack = window.__timeAttack || { stream: null, done: new Set() });

// Phones (iOS Safari especially) only allow sound and audio processing that a tap started.
// Only the first turn begins with a tap, so create the audio engine and the player once, then,
// and reuse them for every later turn; a new AudioContext or Audio() without a tap stays silent.
function audioEngine() {
  if (!shared.context || shared.context.state === "closed") {
    shared.context = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (shared.context.state === "suspended") shared.context.resume().catch(() => {});
  return shared.context;
}

function player() {
  if (!shared.player) {
    shared.player = new Audio();
    shared.player.setAttribute("playsinline", "");
  }
  return shared.player;
}

async function microphone() {
  if (!shared.stream || !shared.stream.active) {
    shared.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
  }
  return shared.stream;
}

function beep(context, frequency = 880, length = 0.12) {
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.frequency.value = frequency;
  gain.gain.setValueAtTime(0.15, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + length);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + length);
}

function toBase64(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(String(reader.result).split(",")[1] || "");
    reader.readAsDataURL(blob);
  });
}

// Glide the page so this turn sits in view: their line above, the timer in the middle.
// Ease-in-out, a bit longer for longer distances; instant if the user prefers less motion,
// and it lets go as soon as the user scrolls themselves.
function glideIntoView(element) {
  const main = document.querySelector('[data-testid="stMain"]');
  if (!main || !element.isConnected) return;
  const view = main.getBoundingClientRect();
  const box = element.getBoundingClientRect();
  const lead = Math.min(160, view.height * 0.22); // room for their line above the card
  const fits = box.top - lead >= view.top && box.bottom <= view.bottom - 24;
  if (fits) return;
  const start = main.scrollTop;
  const target = Math.max(0, start + box.top - view.top - lead);
  const distance = target - start;
  if (Math.abs(distance) < 4) return;
  if (document.hidden || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    main.scrollTop = target;
    return;
  }
  const duration = Math.min(900, Math.max(380, Math.abs(distance) * 0.7));
  const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  let cancelled = false;
  const cancel = () => (cancelled = true);
  main.addEventListener("wheel", cancel, { once: true, passive: true });
  main.addEventListener("touchstart", cancel, { once: true, passive: true });
  const began = performance.now();
  const step = (now) => {
    if (cancelled) return;
    const progress = Math.min(1, (now - began) / duration);
    main.scrollTop = start + distance * ease(progress);
    if (progress < 1) requestAnimationFrame(step);
    else {
      main.removeEventListener("wheel", cancel);
      main.removeEventListener("touchstart", cancel);
    }
  };
  requestAnimationFrame(step);
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const say = (text) => (data.labels && data.labels[text]) || text; // wording in the learner's language
  const root = parentElement.querySelector(".ta") || document.createElement("div");
  root.className = "ta" + (data.dark ? " dark" : "");
  if (!root.parentNode) parentElement.appendChild(root);

  const finished = shared.done.has(data.turn_id);
  root.innerHTML = `
    <div class="ta-head">
      <span class="ta-speaker"></span>
      <span class="ta-limit"></span>
    </div>
    <div class="ta-task"></div>
    <div class="ta-stage">
      <div class="ta-ring"><svg viewBox="0 0 120 120">
        <circle class="ta-track" cx="60" cy="60" r="52"></circle>
        <circle class="ta-left" cx="60" cy="60" r="52"></circle>
      </svg><button class="ta-button" type="button"></button></div>
      <div class="ta-status" aria-live="polite"></div>
    </div>`;
  root.querySelector(".ta-speaker").textContent = data.speaker;
  root.querySelector(".ta-task").textContent = `🎯 ${data.task}`;
  root.querySelector(".ta-limit").textContent = `⏱️ ${data.limit_text || `${data.limit.toFixed(1)} s to answer`}`;
  const button = root.querySelector(".ta-button");
  const status = root.querySelector(".ta-status");
  const ring = root.querySelector(".ta-left");
  const circumference = 2 * Math.PI * 52;
  ring.style.strokeDasharray = `${circumference}`;

  const show = (label, text, state) => {
    button.textContent = label;
    status.textContent = text;
    root.dataset.state = state;
  };

  if (finished) {
    show("✓", say("Answer sent. Checking…"), "done");
    button.disabled = true;
    return;
  }

  async function run() {
    button.disabled = true;
    audioEngine(); // inside the tap on the first turn: unlocks sound for every later turn
    player();
    let stream;
    try {
      stream = await microphone();
    } catch (error) {
      show("🎙️", say("Microphone blocked. Allow it in the browser and try again."), "idle");
      button.disabled = false;
      return;
    }
    const context = audioEngine();
    if (context.state === "suspended") await context.resume().catch(() => {});

    // 1. The other person speaks
    show("🔊", data.listen_text, "listening");
    if (data.audio) {
      const voice = player();
      voice.src = data.audio;
      await new Promise((resolve) => {
        voice.onended = resolve;
        voice.onerror = resolve;
        voice.play().catch(resolve);
      });
    }

    // 2. Your turn: record by itself, with a time limit
    beep(context);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    const source = context.createMediaStreamSource(stream);
    source.connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    const recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
    recorder.start();
    const started = performance.now();
    let firstSpeech = null, speechTime = 0, lastLoud = null, last = started;
    show("🎙️", say("Your turn: speak now!"), "recording");

    await new Promise((resolve) => {
      const tick = (now) => {
        const elapsed = (now - started) / 1000;
        analyser.getFloatTimeDomainData(samples);
        const level = Math.sqrt(samples.reduce((sum, s) => sum + s * s, 0) / samples.length);
        if (level > SPEECH_LEVEL) {
          if (firstSpeech === null) firstSpeech = elapsed;
          speechTime += (now - last) / 1000;
          lastLoud = elapsed;
        }
        last = now;
        const left = Math.max(0, 1 - elapsed / data.limit);
        ring.style.strokeDashoffset = `${circumference * (1 - left)}`;
        root.classList.toggle("ta-hurry", left < 0.3);
        const quietAfterSpeech = speechTime >= MIN_SPEECH && lastLoud !== null && elapsed - lastLoud > END_SILENCE;
        if (elapsed >= data.limit || quietAfterSpeech) return resolve();
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });

    const stopped = new Promise((resolve) => (recorder.onstop = resolve));
    recorder.stop();
    await stopped;
    beep(context, 520);
    source.disconnect(); // keep the engine for the next turn (see audioEngine)
    const spoke = speechTime >= MIN_SPEECH;
    show(spoke ? "✓" : "⏰", spoke ? say("Got it. Checking…") : say("Time's up!"), "done");
    shared.done.add(data.turn_id);
    const audio = spoke ? await toBase64(new Blob(chunks, { type: recorder.mimeType })) : "";
    setTriggerValue("answer", {
      turn_id: data.turn_id,
      audio,
      spoke,
      latency: firstSpeech === null ? null : Math.round(firstSpeech * 10) / 10,
      mime: (recorder.mimeType || "audio/webm").split(";")[0], // so the app can play it back
    });
  }

  // wait a moment for Streamlit to finish drawing the turn, then glide to it
  setTimeout(() => glideIntoView(root), 120);

  if (data.autostart) {
    run();
  } else {
    show("▶", say("Press start. Their line plays, then you have to answer in time."), "idle");
    button.onclick = run;
  }
}
