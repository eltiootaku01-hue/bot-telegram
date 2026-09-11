from __future__ import annotations

import json
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:11434"
MODEL = "qwen3:1.7b"


def request(path: str, payload: dict | None = None, timeout: float = 5.0):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    tags = request("/api/tags")
    models = {item.get("name") for item in tags.get("models", []) if isinstance(item, dict)}
    print("OLLAMA_OK=1")
    print("MODEL_PRESENT=", MODEL in models)
    if MODEL not in models:
        print("Falta el modelo. Ejecuta: ollama pull qwen3:1.7b")
        return 2

    result = request(
        "/api/generate",
        {
            "model": MODEL,
            "prompt": "Responde en español con una sola frase breve: ¿estás listo para trabajar?",
            "stream": False,
            "think": False,
            "keep_alive": 0,
        },
        timeout=90.0,
    )
    print("RESPONSE=", result.get("response", ""))
    print("EVAL_TOKENS=", result.get("eval_count"))
    print("EVAL_NS=", result.get("eval_duration"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
