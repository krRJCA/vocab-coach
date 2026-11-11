// Onboarding tours: a layer over the real site that spotlights one part at a time,
// with Back / Next / Skip. Runs in the page itself (Streamlit components v2), so it can
// highlight anything: the lesson cards, the sidebar settings, the menu, a lesson's tabs.
//
// data.id       which tour ("home", "lesson"); each remembers on its own that it was seen
// data.steps    [{target, title, body, page, tab}]
//                 target: CSS selectors ("a|b" = fallbacks), or "tab:N" for a lesson tab;
//                 none = a centred card. page: an element only on this page (the tour closes
//                 if the learner leaves). tab: open this lesson tab (0-4) for the step.
// data.labels   {next, back, skip, done, start, of}
// data.auto     true when Python sees no saved progress (a first-time learner)
// data.force    dev: start even with saved progress
// data.replay   goes up when someone presses "Take the tour"
// data.reset    dev: goes up when someone presses "Reset tours"
// data.finish   "start_lesson": the last button tells Python to open the first lesson
//
// A tour starts by itself only for first-time learners: never if this browser has saved
// progress or has already seen (or skipped) that tour.

const PROGRESS = "vocab-coach-progress";
const tour = (window.__vocabTour = window.__vocabTour || {
  open: false, replay: {}, autoTried: {}, reset: null,
});

const seenKey = (id) => `vocab-coach-tour-seen-${id}`;

function stored(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (error) {
    return null; // private mode or blocked storage
  }
}

function remember(id) {
  try {
    window.localStorage.setItem(seenKey(id), "1");
  } catch (error) {
    // blocked storage: the tour may show again next visit, which is harmless
  }
}

function hasSavedProgress() {
  try {
    const saved = JSON.parse(stored(PROGRESS) || "{}");
    return Object.keys(saved.progress || {}).length > 0 || Object.keys(saved.tests || {}).length > 0;
  } catch (error) {
    return false;
  }
}

function forget() {
  try {
    Object.keys(window.localStorage)
      .filter((key) => key.startsWith("vocab-coach-tour-seen"))
      .forEach((key) => window.localStorage.removeItem(key));
  } catch (error) {
    // blocked storage: nothing was remembered anyway
  }
}

function lessonTab(n) {
  return document.querySelectorAll('[class*="st-key-tabs-"] [role="tab"]')[n] || null;
}

function find(selectors) {
  if (!selectors) return null;
  for (const selector of selectors.split("|")) {
    const element = selector.startsWith("tab:")
      ? lessonTab(Number(selector.slice(4)))
      : document.querySelector(selector.trim());
    if (!element) continue;
    const box = element.getBoundingClientRect();
    const hidden = box.width < 2 || box.height < 2 || box.right < 0 || box.left > window.innerWidth;
    if (!hidden) return element;
  }
  return null;
}

function calm() {
  // hidden tabs don't run smooth scrolling or animations, so jump instead
  return document.hidden || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function bringIntoView(element, smooth = true) {
  const main = document.querySelector('[data-testid="stMain"]');
  if (!main || !main.contains(element)) return;
  const box = element.getBoundingClientRect();
  const view = main.getBoundingClientRect();
  const room = window.innerHeight * 0.55;
  if (box.top < view.top + 70 || box.bottom > view.top + room) {
    const top = main.scrollTop + box.top - view.top - 90;
    main.scrollTo({ top: Math.max(0, top), behavior: smooth && !calm() ? "smooth" : "auto" });
  }
}

function build(labels) {
  const layer = document.createElement("div");
  layer.className = "vc-tour";
  layer.innerHTML = `
    <div class="vc-tour-shade"></div>
    <div class="vc-tour-spot"></div>
    <div class="vc-tour-card" role="dialog" aria-modal="true" aria-labelledby="vc-tour-title">
      <div class="vc-tour-top">
        <span class="vc-tour-count"></span>
        <button type="button" class="vc-tour-skip">${labels.skip}</button>
      </div>
      <h3 id="vc-tour-title" class="vc-tour-title"></h3>
      <p class="vc-tour-body"></p>
      <div class="vc-tour-dots" aria-hidden="true"></div>
      <div class="vc-tour-buttons">
        <button type="button" class="vc-tour-back">${labels.back}</button>
        <button type="button" class="vc-tour-next"></button>
      </div>
    </div>`;
  document.body.appendChild(layer);
  return layer;
}

function place(layer, element) {
  const spot = layer.querySelector(".vc-tour-spot");
  const card = layer.querySelector(".vc-tour-card");
  const phone = window.innerWidth < 640;
  layer.classList.toggle("vc-tour-centred", !element);
  layer.classList.toggle("vc-tour-phone", phone);
  if (!element) {
    spot.style.cssText = "";
    card.style.cssText = "";
    return;
  }
  const pad = 8;
  const box = element.getBoundingClientRect();
  const top = Math.max(4, box.top - pad);
  const left = Math.max(4, box.left - pad);
  const width = Math.min(window.innerWidth - 8, box.right + pad) - left;
  const height = Math.min(window.innerHeight - 8, box.bottom + pad) - top;
  spot.style.cssText = `top:${top}px;left:${left}px;width:${width}px;height:${height}px`;
  if (phone) {
    // a sheet at the bottom, or at the top when the highlighted part is low on the screen
    const low = top + height / 2 > window.innerHeight * 0.55;
    card.style.cssText = low ? "top:12px;bottom:auto" : "";
    return;
  }
  const cardWidth = card.offsetWidth;
  const cardHeight = card.offsetHeight;
  let cardTop = top + height + 14;
  if (cardTop + cardHeight > window.innerHeight - 12) cardTop = top - cardHeight - 14;
  let cardLeft = left;
  if (cardTop < 12) {
    // no room above or below: put it beside the part
    cardTop = Math.min(Math.max(12, top), window.innerHeight - cardHeight - 12);
    cardLeft = left + width + 14 + cardWidth < window.innerWidth ? left + width + 14 : left - cardWidth - 14;
  }
  cardLeft = Math.min(Math.max(12, cardLeft), window.innerWidth - cardWidth - 12);
  card.style.cssText = `top:${cardTop}px;left:${cardLeft}px`;
}

function start(data, setTriggerValue) {
  if (tour.open) return;
  const steps = data.steps || [];
  if (!steps.length) return;
  const labels = data.labels;
  const layer = build(labels);
  const card = layer.querySelector(".vc-tour-card");
  const dots = layer.querySelector(".vc-tour-dots");
  dots.innerHTML = steps.map(() => "<span></span>").join("");
  let index = 0;
  let target = null;
  let frame = 0;
  let missingSince = 0;
  tour.open = true;

  const follow = () => {
    // keep the spotlight on its part while the page scrolls, resizes or reruns
    if (!document.body.contains(layer)) return;
    const step = steps[index];
    if (step.target && (!target || !document.body.contains(target))) target = find(step.target);
    place(layer, target);
    // left the home page (e.g. clicked a menu link): close quietly
    if (step.page && !document.querySelector(step.page)) {
      missingSince = missingSince || Date.now();
      if (Date.now() - missingSince > 800) return close(false);
    } else {
      missingSince = 0;
    }
    frame = window.requestAnimationFrame(follow);
  };

  const show = (next) => {
    index = Math.max(0, Math.min(steps.length - 1, next));
    const step = steps[index];
    // show that tab's content behind the card (a click, like the learner's own)
    const tab = step.tab !== undefined && step.tab !== null ? lessonTab(step.tab) : null;
    if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
    target = find(step.target);
    if (target) bringIntoView(target);
    layer.querySelector(".vc-tour-count").textContent = labels.of
      .replace("{n}", index + 1)
      .replace("{total}", steps.length);
    layer.querySelector(".vc-tour-title").textContent = step.title;
    layer.querySelector(".vc-tour-body").innerHTML = step.body;
    layer.querySelector(".vc-tour-back").hidden = index === 0;
    const last = index === steps.length - 1;
    layer.querySelector(".vc-tour-next").textContent = last ? labels.start : labels.next;
    layer.querySelector(".vc-tour-skip").textContent = last ? labels.done : labels.skip;
    [...dots.children].forEach((dot, i) => dot.classList.toggle("on", i === index));
    card.classList.remove("vc-tour-enter");
    void card.offsetWidth; // restart the little entrance animation
    card.classList.add("vc-tour-enter");
    layer.querySelector(".vc-tour-next").focus({ preventScroll: true });
    place(layer, target);
    // the page may still be scrolling the part into view: settle the spotlight after it
    // (and if smooth scrolling didn't happen, e.g. a background tab, jump there instead)
    const settle = () => {
      if (!tour.open || steps[index] !== step) return;
      // a tab click made while the page was still redrawing can be lost: press it again
      const wanted = step.tab !== undefined && step.tab !== null ? lessonTab(step.tab) : null;
      if (wanted && wanted.getAttribute("aria-selected") !== "true") wanted.click();
      target = find(step.target) || target;
      if (target) bringIntoView(target, false);
      place(layer, target);
    };
    setTimeout(settle, 600);
    setTimeout(settle, 1400);
  };
  const reposition = () => tour.open && place(layer, target);

  const close = (finished) => {
    window.cancelAnimationFrame(frame);
    document.removeEventListener("keydown", keys, true);
    window.removeEventListener("resize", reposition);
    document.removeEventListener("scroll", reposition, true);
    layer.remove();
    tour.open = false;
    remember(data.id);
    // back to the first tab, where a lesson starts
    const first = steps.some((step) => step.tab !== undefined && step.tab !== null) ? lessonTab(0) : null;
    if (first && first.getAttribute("aria-selected") !== "true") first.click();
    if (finished && data.finish) setTriggerValue(data.finish, Date.now());
  };

  const keys = (event) => {
    if (event.key === "Escape") close(false);
    else if (event.key === "ArrowRight") index < steps.length - 1 && show(index + 1);
    else if (event.key === "ArrowLeft") show(index - 1);
    else return;
    event.preventDefault();
    event.stopPropagation();
  };

  layer.querySelector(".vc-tour-next").addEventListener("click", () =>
    index === steps.length - 1 ? close(true) : show(index + 1)
  );
  layer.querySelector(".vc-tour-back").addEventListener("click", () => show(index - 1));
  layer.querySelector(".vc-tour-skip").addEventListener("click", () => close(false));
  layer.querySelector(".vc-tour-shade").addEventListener("click", () => show(index + 1 < steps.length ? index + 1 : index));
  document.addEventListener("keydown", keys, true);
  window.addEventListener("resize", reposition);
  document.addEventListener("scroll", reposition, true); // Streamlit scrolls an inner panel
  show(0);
  frame = window.requestAnimationFrame(follow);
}

export default function (component) {
  const { data, setTriggerValue } = component;
  if (!data || !data.steps) return;
  const id = data.id;
  // dev "Reset tours": forget that any tour was seen, so they start by themselves again
  if (tour.reset === null) tour.reset = data.reset || 0;
  if (data.reset && data.reset !== tour.reset) {
    tour.reset = data.reset;
    forget();
    tour.autoTried = {};
  }
  // "Take the tour" pressed: the replay number changed since this tour last saw it
  if (tour.replay[id] === undefined) tour.replay[id] = data.replay || 0;
  if (data.replay && data.replay !== tour.replay[id]) {
    tour.replay[id] = data.replay;
    setTimeout(() => start(data, setTriggerValue), 150);
    return;
  }
  // first-time learner only: nothing saved in this browser, and this tour not seen yet
  const firstTime = data.force || (data.auto && !hasSavedProgress());
  if (firstTime && !tour.autoTried[id] && !stored(seenKey(id))) {
    tour.autoTried[id] = true; // once per page load, however often Streamlit reruns
    setTimeout(() => start(data, setTriggerValue), 900); // let the page settle first
  }
}
