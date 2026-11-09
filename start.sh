#!/bin/sh
# Start the app on Hugging Face. The Space's secrets arrive as environment variables;
# Streamlit's Google sign-in reads them from .streamlit/secrets.toml, so write that file first.
# Without GOOGLE_CLIENT_ID the app runs without sign-in (fine for a local docker test).
set -e

if [ -n "$GOOGLE_CLIENT_ID" ]; then
  python3 - <<'EOF'
import json, os
admins = [e.strip() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]
q = json.dumps  # TOML basic strings use the same escaping as JSON
with open(".streamlit/secrets.toml", "w") as f:
    f.write(f"admins = {q(admins)}\n\n")
    f.write("[auth]\n")
    f.write(f"redirect_uri = {q(os.environ['AUTH_REDIRECT_URI'])}\n")
    f.write(f"cookie_secret = {q(os.environ['AUTH_COOKIE_SECRET'])}\n\n")
    f.write("[auth.google]\n")
    f.write(f"client_id = {q(os.environ['GOOGLE_CLIENT_ID'])}\n")
    f.write(f"client_secret = {q(os.environ['GOOGLE_CLIENT_SECRET'])}\n")
    f.write('server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"\n')
EOF
fi

exec /home/user/venv/bin/streamlit run app.py \
  --server.port 7860 --server.address 0.0.0.0 --server.headless true
