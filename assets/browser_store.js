// Keeps a learner's progress in their own browser (localStorage), when the app runs online
// without sign-in. Nothing is stored on the server, so it survives refreshes and server
// restarts, but it stays on this browser and device.
//
// data.mode "load": send what this browser has saved back to Python (once per page load).
// data.save {version, progress, tests}: write it, unless this browser already has a newer version.

const KEY = "vocab-coach-progress";

function read() {
  try {
    return JSON.parse(window.localStorage.getItem(KEY) || "{}");
  } catch (error) {
    return {}; // private mode or blocked storage: start fresh
  }
}

export default function (component) {
  const { data, setTriggerValue } = component;
  if (data.mode === "load") {
    setTriggerValue("loaded", read());
  }
  if (data.save) {
    try {
      if ((data.save.version || 0) > (read().version || 0)) {
        window.localStorage.setItem(KEY, JSON.stringify(data.save));
      }
    } catch (error) {
      // storage full or blocked: progress just won't be kept after this visit
    }
  }
}
