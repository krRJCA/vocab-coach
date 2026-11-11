// A light / dark switch in the top-right bar, next to Streamlit's ⋮ menu.
//
// Streamlit already has a theme choice (⋮ → Light / Dark), which switches instantly and is
// remembered in this browser. This button uses that same choice: it opens the menu out of
// sight, presses Light or Dark, and closes it, so there's no reload and the learner keeps
// their place.
//
// data.labels {light, dark}: the button's tooltip ("Switch to light mode", ...)

const ID = "vc-theme-switch";
const SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
const MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>';

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function isDark() {
  // read the page itself, so "System" (follow the device) is handled too
  const app = document.querySelector(".stApp") || document.body;
  const [r, g, b] = (getComputedStyle(app).backgroundColor.match(/\d+/g) || [255, 255, 255]).map(Number);
  return 0.299 * r + 0.587 * g + 0.114 * b < 128;
}

async function choose(theme) {
  const menuButton = document.querySelector('[data-testid="stMainMenuButton"] button, [data-testid="stMainMenuButton"]');
  if (!menuButton) return;
  const hide = document.createElement("style");
  // keep the menu invisible while it's used behind the scenes (its box and anything around it)
  hide.textContent = '[data-testid="stMainMenuPopover"], [data-testid="stMainMenuPopover"] *, ' +
    '[data-baseweb="popover"]:has([data-testid="stMainMenuPopover"]) ' +
    '{ opacity: 0 !important; pointer-events: none !important; transition: none !important; animation: none !important; }';
  document.head.appendChild(hide);
  try {
    menuButton.click();
    let item = null;
    for (let tries = 0; tries < 20 && !item; tries++) {
      await wait(25);
      item = document.querySelector(`[data-testid="stMainMenuItem-theme-${theme}"]`);
    }
    if (item) item.click();
    await wait(50);
    if (document.querySelector('[data-testid^="stMainMenuItem-theme-"]')) {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    }
  } finally {
    // stay hidden until the menu has really closed (it fades out)
    for (let tries = 0; tries < 40 && document.querySelector('[data-testid="stMainMenuPopover"]'); tries++) {
      await wait(25);
    }
    await wait(150);
    hide.remove();
  }
}

function sync() {
  // tells the app's own CSS which theme is showing (light-only rules use html[data-vc-theme=light])
  const theme = isDark() ? "dark" : "light";
  if (document.documentElement.dataset.vcTheme !== theme) document.documentElement.dataset.vcTheme = theme;
  return theme === "dark";
}

function refresh(button, labels) {
  const dark = sync();
  const label = dark ? labels.light : labels.dark;
  if (button.__dark === dark && button.title === label) return; // nothing changed
  button.__dark = dark;
  button.innerHTML = dark ? SUN : MOON;
  button.title = label;
  button.setAttribute("aria-label", label);
}

export default function (component) {
  const { data } = component;
  const labels = (data && data.labels) || { light: "Light mode", dark: "Dark mode" };
  const place = () => {
    const bar = document.querySelector('[data-testid="stToolbarActions"]') ||
      document.querySelector('[data-testid="stToolbar"]');
    const menu = document.querySelector('[data-testid="stMainMenu"]');
    if (!bar && !menu) return false;
    let button = document.getElementById(ID);
    if (!button) {
      button = document.createElement("button");
      button.id = ID;
      button.type = "button";
      button.className = "vc-theme-switch";
      button.addEventListener("click", async () => {
        await choose(isDark() ? "Light" : "Dark");
        setTimeout(() => refresh(button, button.__labels), 120);
      });
      if (menu && menu.parentNode) menu.parentNode.insertBefore(button, menu);
      else bar.appendChild(button);
    }
    button.__labels = labels; // the language may have changed
    refresh(button, labels);
    return true;
  };
  sync();
  if (!place()) setTimeout(place, 500); // the bar may not be drawn yet
  // follow any theme change: this button, Streamlit's ⋮ menu, or the device ("System")
  if (!window.__vcThemeWatch) {
    window.__vcThemeWatch = setInterval(() => {
      sync();
      const button = document.getElementById(ID);
      if (button && button.__labels) refresh(button, button.__labels);
    }, 400);
  }
}
