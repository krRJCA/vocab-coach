"""Qwen3-ASR helper process (runs in its own environment, see qwen/requirements.txt).

The app (speech.py) starts this once and talks to it over stdin/stdout, one JSON line each way:
    -> {"id": 1, "path": "/tmp/answer.wav", "context": "lesson phrases"}
    <- {"id": 1, "text": "카드 돼요?", "seconds": 0.6}
The first line it prints is {"ready": true} once the model is loaded.
"""

import json
import sys
import time

import torch
from qwen_asr import Qwen3ASRModel

MODEL_NAME = "Qwen/Qwen3-ASR-0.6B"


def main():
    model = Qwen3ASRModel.from_pretrained(
        MODEL_NAME, dtype=torch.float32, device_map="cpu", max_new_tokens=64,
    )
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        start = time.time()
        try:
            result = model.transcribe(audio=request["path"], context=request.get("context", ""),
                                      language="Korean")[0]
            reply = {"id": request["id"], "text": result.text.strip(),
                     "seconds": round(time.time() - start, 2)}
        except Exception as error:  # report, don't die: the app shows the error
            reply = {"id": request["id"], "error": f"{type(error).__name__}: {error}"}
        print(json.dumps(reply, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
