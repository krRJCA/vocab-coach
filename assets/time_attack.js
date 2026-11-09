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

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector(".ta") || document.createElement("div");
  root.className = "ta" + (data.dark ? " dark" : "");
  if (!root.parentNode) parentElement.appendChild(root);

  const finished = shared.done.has(data.turn_id);
  root.innerHTML = `
    <div class="ta-head">
      <span class="ta-speaker"></span>
      <span class="ta-limit">⏱️ ${data.limit.toFixed(1)} s to answer</span>
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
    show("✓", "Answer sent. Checking…", "done");
    button.disabled = true;
    return;
  }

  async function run() {
    button.disabled = true;
    let stream;
    try {
      stream = await microphone();
    } catch (error) {
      show("🎙️", "Microphone blocked. Allow it in the browser and try again.", "idle");
      button.disabled = false;
      return;
    }
    const context = new AudioContext();

    // 1. The other person speaks
    show("🔊", data.listen_text, "listening");
    if (data.audio) {
      const voice = new Audio(data.audio);
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
    context.createMediaStreamSource(stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    const recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
    recorder.start();
    const started = performance.now();
    let firstSpeech = null, speechTime = 0, lastLoud = null, last = started;
    show("🎙️", "Your turn: speak now!", "recording");

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
    context.close();
    const spoke = speechTime >= MIN_SPEECH;
    show(spoke ? "✓" : "⏰", spoke ? "Got it. Checking…" : "Time's up!", "done");
    shared.done.add(data.turn_id);
    const audio = spoke ? await toBase64(new Blob(chunks, { type: recorder.mimeType })) : "";
    setTriggerValue("answer", {
      turn_id: data.turn_id,
      audio,
      spoke,
      latency: firstSpeech === null ? null : Math.round(firstSpeech * 10) / 10,
    });
  }

  if (data.autostart) {
    run();
  } else {
    show("▶", "Press start. Their line plays, then you have to answer in time.", "idle");
    button.onclick = run;
  }
}
