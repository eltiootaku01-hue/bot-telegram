from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from typing import Callable

import keyring


class DynamicLLMPool:
    SERVICE = "cafe-otaku.llm"

    @classmethod
    def configs(cls) -> list[dict]:
        try:
            raw = keyring.get_password(cls.SERVICE, "pool_config") or "[]"
            value = json.loads(raw)
        except Exception:
            return []
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            provider_id = str(item.get("id", "")).strip()
            if not provider_id:
                continue
            try:
                item = dict(item)
                item["api_key"] = keyring.get_password(cls.SERVICE, f"provider:{provider_id}") or ""
            except Exception:
                item = dict(item)
                item["api_key"] = ""
            if item["api_key"]:
                result.append(item)
        return sorted(result, key=lambda item: (int(item.get("priority", 999)), str(item.get("alias", "")).casefold()))

    @classmethod
    def generate(
        cls,
        provider: dict,
        request,
        post_json: Callable[[str, dict, dict], dict],
        messages: Callable[[object], list[dict[str, str]]],
        system_prompt: Callable[[object], str],
    ) -> str:
        name = str(provider.get("provider", "")).casefold()
        key = str(provider.get("api_key", "")).strip()
        if not key:
            raise RuntimeError("API key not configured")
        if name in {"openai", "groq"}:
            base = str(provider.get("endpoint", "")).strip()
            if not base:
                base = "https://api.groq.com/openai/v1" if name == "groq" else "https://api.openai.com/v1"
            url = base if base.endswith("/chat/completions") else base.rstrip("/") + "/chat/completions"
            model = str(provider.get("model", "")).strip() or ("llama-3.3-70b-versatile" if name == "groq" else "gpt-5-mini")
            data = post_json(url, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                             {"model": model, "messages": messages(request), "temperature": request.temperature, "max_tokens": request.max_tokens})
            return str(data["choices"][0]["message"]["content"])
        if name == "hugging face":
            model = str(provider.get("model", "")).strip()
            if not model:
                raise RuntimeError("Hugging Face model is required")
            url = str(provider.get("endpoint", "")).strip() or f"https://api-inference.huggingface.co/models/{model}"
            data = post_json(url, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                             {"inputs": request.user_text[:request.max_user_chars]})
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return str(data[0].get("generated_text", ""))
            if isinstance(data, dict) and data.get("generated_text"):
                return str(data["generated_text"])
            raise RuntimeError("Invalid Hugging Face response")
        if name == "google gemini":
            model = str(provider.get("model", "")).strip() or "gemini-2.5-flash"
            url = str(provider.get("endpoint", "")).strip() or f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            contents = [{"role": "user", "parts": [{"text": x[:800]}]} for x in request.recent_context[-8:]]
            contents.append({"role": "user", "parts": [{"text": request.user_text[:request.max_user_chars]}]})
            data = post_json(url, {"Content-Type": "application/json", "x-goog-api-key": key},
                             {"system_instruction": {"parts": [{"text": system_prompt(request)}]}, "contents": contents,
                              "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens}})
            return " ".join(str(part.get("text", "")) for part in data["candidates"][0]["content"]["parts"])
        if name == "custom rest":
            url = str(provider.get("endpoint", "")).strip()
            if not url:
                raise RuntimeError("Custom REST endpoint is required")
            payload = {"messages": messages(request)}
            if provider.get("model"):
                payload["model"] = str(provider["model"])
            data = post_json(url, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, payload)
            candidates = [
                data.get("text"), data.get("response"), data.get("output"),
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content"),
            ]
            for value in candidates:
                if isinstance(value, str) and value.strip():
                    return value
            raise RuntimeError("Custom REST response has no text")
        raise RuntimeError(f"Unsupported provider: {provider.get('provider')}")

    @staticmethod
    def offline(request, database_url: str) -> str:
        path = database_url.split(":///", 1)[1].split("?", 1)[0] if ":///" in database_url else database_url
        path = os.path.abspath(path or "data/bot.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        defaults = {
            "cari": "Estoy en modo offline por ahora, pero sigo acá. Decime qué necesitás.",
            "sunna": "Modo offline. Las funciones locales siguen disponibles.",
            "cami": "La conexión LLM no está disponible. El modo local sigue operativo.",
            "chie": "Estoy trabajando en modo offline. Las funciones locales siguen disponibles.",
        }
        identity = request.identity.value
        fallback = defaults.get(identity, "Modo offline activo. Las funciones locales siguen disponibles.")
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS llm_offline_responses (id INTEGER PRIMARY KEY AUTOINCREMENT, identity TEXT NOT NULL, response TEXT NOT NULL)")
            if conn.execute("SELECT COUNT(*) FROM llm_offline_responses WHERE identity=?", (identity,)).fetchone()[0] == 0:
                conn.execute("INSERT INTO llm_offline_responses(identity,response) VALUES(?,?)", (identity, fallback))
                conn.commit()
            rows = conn.execute("SELECT response FROM llm_offline_responses WHERE identity=? ORDER BY id", (identity,)).fetchall()
        index = int(hashlib.sha256(request.user_text.encode("utf-8")).hexdigest(), 16) % len(rows)
        return str(rows[index][0]) if rows else fallback
