from pathlib import Path
import time
import requests

ROOT = Path(r"C:\Users\USER\Documents\Codex\2026-09-04\referenced-chatgpt-conversation-this-is-an\one-neko-punch")

files = [
    ROOT / "characters" / "001.na-y-cuerpo-maid-gata.md",
    ROOT / "characters" / "002.entidad-gata-negra.md",
    ROOT / "world" / "canon-one-neko-punch" / "001.cronologia-y-ledger.md",
]

def extract_relevant(text: str, max_chars: int = 2400) -> str:
    lines = text.splitlines()

    wanted = (
        "Hechos confirmados en manuscrito",
        "Hechos mostrados",
        "Identidad y nombre",
        "Estado",
        "Pendiente",
        "Planificado",
        "Mostrado",
        "Reglas",
    )

    selected = []
    capture = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("#"):
            capture = any(section.lower() in stripped.lower() for section in wanted)

        if capture:
            selected.append(line)

    result = "\n".join(selected).strip()

    if not result:
        result = text[:max_chars]

    return result[:max_chars]


parts = []

for path in files:
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")

    text = path.read_text(encoding="utf-8")
    relevant = extract_relevant(text)

    parts.append(
        f"\n===== FUENTE: {path.name} =====\n"
        f"{relevant}"
    )

context = "\n".join(parts)

prompt = f"""
Eres IA-Chan, asistente de escritura especializado en trabajar con una biblioteca narrativa.

REGLAS:
- Usa únicamente la información del contexto.
- No inventes hechos del universo.
- Distingue HECHO, PLANIFICACIÓN y PENDIENTE.
- Si algo no está establecido, dilo.
- Puedes hacer propuestas creativas, pero deben estar marcadas como PROPUESTA.
- Responde en español.
- No uses conocimiento externo sobre nombres o personajes.
- La documentación proporcionada tiene prioridad absoluta.

CONTEXTO:
{context}

TAREA:
Analiza la relación y diferencia entre Kuro y Yume Kuro.

Responde en exactamente estas secciones:

HECHOS:
Qué está establecido.

PLANIFICACIÓN:
Qué aparece como planificación o decisión aprobada, pero aún no como hecho mostrado.

PENDIENTE:
Qué no está establecido.

PROPUESTA:
Una idea breve para una escena futura entre ambas que no contradiga los puntos anteriores.
"""

models = [
    "gemma3:latest",
    "gemma3:4b-it-qat",
]

print("=" * 70)
print("PRUEBA CONTROLADA DE IA-CHAN / OLLAMA")
print("=" * 70)
print(f"Contexto enviado: {len(context)} caracteres")
print()

for model in models:
    print("=" * 70)
    print(f"MODELO: {model}")
    print("=" * 70)

    start = time.perf_counter()

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
            },
        },
        timeout=180,
    )

    elapsed = time.perf_counter() - start

    response.raise_for_status()
    data = response.json()

    print()
    print(data.get("response", ""))

    prompt_tokens = data.get("prompt_eval_count") or 0
    output_tokens = data.get("eval_count") or 0

    print()
    print("--- METRICAS ---")
    print(f"Tiempo total: {elapsed:.2f} s")
    print(f"Tokens entrada: {prompt_tokens}")
    print(f"Tokens salida: {output_tokens}")
    print(f"Tokens totales: {prompt_tokens + output_tokens}")

    if output_tokens and data.get("eval_duration"):
        tokens_per_sec = output_tokens / (data["eval_duration"] / 1_000_000_000)
        print(f"Velocidad salida: {tokens_per_sec:.2f} tokens/s")

    print()
