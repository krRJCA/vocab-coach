# Deploying the app

The app runs for free on **Streamlit Community Cloud**, in a lighter version with **Whisper small
only** (it needs about 0.8 GB of memory). The full version with all three speech models needs
Hugging Face Spaces, which now requires a PRO subscription ($9/month); see the end of this page.

What learners get online:

- **No accounts.** Anyone with the link can use it.
- **Progress is saved in each learner's own browser** (local storage), never on the server. It
  stays when they refresh or come back later, and survives server restarts and updates. It does
  **not** follow them to another device or browser, and clearing browser data deletes it. The app
  says so on screen: *"Your progress is saved only in this browser, on this device."*
- **One team password** (the `TEAM_PASSWORD` secret) unlocks the team-only parts: the
  **survey results** and the **🔬 Model lab**. Entering it once unlocks both for that visit.
  Survey answers are stored on the server, so a restart clears them: check the results before
  you push an update.
- **Dev-only tools never go online.** 🎧 Voice check (marked ᵈᵉᵛ in the tabs on your Mac), the
  voice-making and test scripts, and your voice review data are listed in `.gitignore` and
  `.dockerignore`, so they're never pushed or deployed. They stay on your computer only.

The app knows it's online by itself: Streamlit Community Cloud runs apps from `/mount/src`, and
there it switches to browser storage and Whisper small only (`speech.allowed_engines()`).

## Streamlit Community Cloud (free)

You need: a GitHub account. About 15 minutes, plus a 5-10 minute first start.

### 1. Put the code on GitHub

Streamlit deploys from a **public** GitHub repository. From the project folder,
after `gh auth login`:

```bash
git init
git branch -M main
git add .
git commit -m "Scenario Vocab Coach"
gh repo create vocab-coach --public --source . --push
```

`.gitignore` keeps out `.venv`, `.venv-qwen`, your own progress, the dev-only tools and any
`secrets.toml`.

### 2. Create the app

1. Go to **share.streamlit.io** and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub**.
3. Repository `<your-github-name>/vocab-coach`, branch `main`, main file `app.py`.
4. Pick an address, e.g. `bufs-vocab-coach.streamlit.app`.
5. **Advanced settings:**
   - Python version **3.12**.
   - Secrets: `TEAM_PASSWORD = "your team password"`.
6. **Deploy.**

Streamlit installs from `uv.lock` (with the CPU-only PyTorch) and `packages.txt` (ffmpeg). The
first start downloads Whisper small and the Korean meaning model, so give it a few minutes.

### Updating later

```bash
git add . && git commit -m "Describe the change" && git push
```

The app restarts by itself. Learners keep their progress, since it lives in their browsers.

### Good to know

- **Sleeping:** apps sleep after about 12 hours without visitors. The next visitor sees a
  "wake up" button and waits about a minute. Learners' progress is unaffected.
- **Memory:** Streamlit doesn't promise exact limits (about 1-2.7 GB). The app measured
  ~0.55 GB after loading Whisper small, plus about 0.25 GB for the meaning model.
- **Try the online behaviour on your Mac:** the `vocab-coach-online-test` dev server (in
  `.claude/launch.json`) runs the app as it runs online: browser storage, Whisper small only,
  hidden dev pages, and the team password `test-password`. Locally you can also set
  `VOCAB_ONLINE=1` and `SPEECH_MODELS=whisper-small` yourself.

## Hugging Face Spaces (all three models, needs PRO)

Since mid-2026, Docker Spaces on the free CPU need a **PRO** subscription ($9/month; you can
cancel after a demo). The Space then runs the full app: Whisper small, Whisper turbo and
Qwen3-ASR, with the live Model lab (2 CPUs, 16 GB memory).

1. huggingface.co → **New → Space**: SDK **Docker** (template Blank), hardware **CPU basic**.
2. **Settings → Variables and secrets → New secret:** `TEAM_PASSWORD`.
3. Hugging Face reads its settings from a header at the very top of `README.md`. Add it (it's left
   out on GitHub, where it would show as a table):

   ```yaml
   ---
   title: Scenario Vocab Coach
   emoji: 🇰🇷
   colorFrom: red
   colorTo: blue
   sdk: docker
   app_port: 7860
   pinned: false
   short_description: Korean phrases for life in Busan, practiced in real scenarios
   ---
   ```

4. Push the same git repository to the Space:

   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/vocab-coach
   git push space main --force
   ```

   (`--force` only the first time, to replace the Space's starter commit.)

The first build takes 20-30 minutes: it installs two Python environments and downloads all
models into a ~14 GB image. Watch it under **Logs → Build**. The Space sleeps after 48 hours
without visitors. To test the image locally (with Docker Desktop running):
`docker build -t vocab-coach .` then `docker run -p 7860:7860 vocab-coach`, and open
http://localhost:7860.

## Optional: require Sign in with Google

If you later want only signed-in people to use the app, the code for it is already in place.
Adding these secrets turns it on. Progress then moves to the server (one anonymous folder per
Google account), so it follows people across devices but resets when the server restarts.

1. At console.cloud.google.com, create a project. On the **OAuth consent screen**, choose audience
   **External**, then add classmates as **Test users** (up to 100) or press **Publish app**.
2. **Clients → Create client → Web application**, with the authorized redirect URI
   `https://<your-app-address>/oauth2callback`.
3. Add these secrets:

| Name | Value |
| --- | --- |
| `GOOGLE_CLIENT_ID` | the client ID |
| `GOOGLE_CLIENT_SECRET` | the client secret |
| `AUTH_REDIRECT_URI` | `https://<your-app-address>/oauth2callback` |
| `AUTH_COOKIE_SECRET` | a long random string: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAILS` | your team's Gmail addresses, comma-separated (they skip the team password) |
