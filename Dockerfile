# Scenario Vocab Coach on Hugging Face Spaces (Docker Space, free CPU: 2 vCPU, 16 GB RAM).
# See DEPLOY.md. Locally: docker build -t vocab-coach . && docker run -p 7860:7860 vocab-coach

FROM python:3.12-slim

# ffmpeg decodes recorded answers (webm) and the voice files
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face runs Spaces as user 1000; give it a home for the model cache
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    UV_PROJECT_ENVIRONMENT=/home/user/venv
WORKDIR /home/user/app

# Install the app's packages (no dev tools: the voices are already made)
RUN pip install --no-cache-dir --user uv
COPY --chown=user pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Qwen3-ASR runs in its own environment (it pins an older transformers), CPU-only PyTorch
COPY --chown=user qwen/requirements.txt qwen/requirements.txt
RUN uv venv /home/user/qwen-venv --python 3.12 \
    && uv pip install --python /home/user/qwen-venv/bin/python \
       --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 \
    && uv pip install --python /home/user/qwen-venv/bin/python -r qwen/requirements.txt
ENV QWEN_PYTHON=/home/user/qwen-venv/bin/python

COPY --chown=user . .

# Download all models now (Whisper small + turbo, the Korean meaning model, Qwen3-ASR),
# so nobody waits for a download later
RUN /home/user/venv/bin/python -c "from coach import speech, semantic; \
speech.load_model('whisper-small'); speech.load_model('whisper-turbo'); semantic.load_model()" \
    && /home/user/qwen-venv/bin/python -c "from qwen_asr import Qwen3ASRModel; \
Qwen3ASRModel.from_pretrained('Qwen/Qwen3-ASR-0.6B')"

EXPOSE 7860
CMD ["sh", "start.sh"]
