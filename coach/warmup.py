"""Load AI models in the background, before a learner needs them.

Opening a lesson starts loading the speech model (and the meaning model) in a background
thread, while the learner reads the Situation and Notice tabs. By the time they record an
answer, the model is usually ready. Opening the website alone loads nothing.

Models are shared by everyone on the server, so this only costs time once per server start.
"""

import threading
import time

_lock = threading.Lock()
_threads = {}


START_DELAY = 3  # seconds: let the lesson page finish drawing first (loading competes with it for the CPU)


def preload(name, load):
    """Start load() in the background once per server (again only if it failed)."""
    with _lock:
        thread = _threads.get(name)
        if thread is not None:
            return
        thread = threading.Thread(target=_run, args=(name, load), daemon=True, name=f"preload-{name}")
        _threads[name] = thread
    thread.start()


def _run(name, load):
    time.sleep(START_DELAY)
    try:
        load()
    except Exception:
        with _lock:
            _threads.pop(name, None)  # let the next lesson (or the first answer) try again


def wait(name):
    """If a background load is running, wait for it instead of loading a second copy."""
    thread = _threads.get(name)
    if thread is not None and thread is not threading.current_thread():
        thread.join()
