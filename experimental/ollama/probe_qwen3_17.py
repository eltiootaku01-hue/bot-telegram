from __future__ import annotations

import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

BASE_URL = "http://127.0.0.1:11434"
MODEL = "qwen3:1.7b-q4_K_M"


def get_json(path: str, timeout: float = 3.0) -> dict:
    request = Request(BASE_URL + path, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def generate() -> int:
    payload = {
        "model": MODEL,
        "prompt": "Responde en español con una sola frase breve. No inventes datos.",
        "stream": False,
        "think": False,
        "keep_alive": 0,
        "options": {"num_predict": 48},
    }
    # Deliberately no Authorization header: this is the API-free local contract.
    request = Request(
        BASE_URL + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urlopen(request, timeout=90.0) as response:
        result = json.loads(response.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    text = result.get("response", "")
    print(f"MODEL={MODEL}")
    print(f"ELAPSED_SECONDS={elapsed:.2f}")
    print(f"EVAL_TOKENS={result.get('eval_count')}")
    print(f"EVAL_NS={result.get('eval_duration')}")
    print(f"RESPONSE={text}")
    return 0 if isinstance(text, str) and text.strip() else 3


def main() -> int:
    try:
        tags = get_json("/api/tags")
    except URLError as error:
        print("OLLAMA_UNREACHABLE=1")
        print(f"ERROR={error}")
        return 2
    models = {item.get("name") for item in tags.get("models", []) if isinstance(item, dict)}
    print("OLLAMA_OK=1")
    if MODEL not in models:
        print(f"MODEL_PRESENT=0")
        print(f"Ejecuta: ollama pull {MODEL}")
        return 2
    print("MODEL_PRESENT=1")
    return generate()


if __name__ == "__main__":
    raise SystemExit(main())
