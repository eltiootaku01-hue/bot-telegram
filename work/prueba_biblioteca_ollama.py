from pathlib import Path
import time
import requests

ROOT = Path(r"C:\Users\USER\Documents\Codex\2026-09-04\referenced-chatgpt-conversation-this-is-an\one-neko-punch")

files = [
    ROOT / "characters" / "001.na-y-cuerpo-maid-gata.md",
    ROOT / "characters" / "002.entidad-gata-negra.md",
    ROOT / "chapters" / "003.companeros-de-cuarto.md",
    ROOT / "world" / "canon-one-neko-punch" / "001.cronologia-y-ledger.md",
    ROOT / "style" / "000.style-guide.md",
]

parts = []

for path in files:
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")
    text = path.read_text(encoding="utf-8")
    parts.append(f"\n===== FUENTE: {path.name} =====\n{text}")

context = "\n".join(parts)

prompt = f"""
Eres IA-Chan, un asistente especializado en trabajar con una biblioteca narrativa.

REGLAS:
- Usa exclusivamente la información proporcionada en el contexto.
- No inventes hechos del universo.
- Distingue hechos mostrados, planificación y elementos pendientes.
- Si algo no está establecido, dilo claramente.
- Puedes proponer ideas creativas, pero debes marcarlas como PROPUESTA.
- Responde en español.
- Analiza el material antes de redactar.

BIBLIOTECA:
{context}

TAREA:
1. Explica qué está establecido actualmente sobre Kuro.
2. Explica qué está establecido actualmente sobre Yume Kuro.
3. Separa claramente HECHO, PLANIFICACIÓN y PENDIENTE.
4. Analiza qué precauciones debería tener una escena futura entre Kuro y Yume Kuro.
5. Propón una breve escena de ejemplo de 300 a 500 palabras que respete las restricciones anteriores.
"""

print("Modelo: gemma3:1b")
print(f"Contexto: {len(context)} caracteres")
print("Iniciando prueba...")

start = time.perf_counter()

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "gemma3:1b",
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

print("\n=== RESULTADO ===")
print(data.get("response", ""))

print("\n=== METRICAS ===")
print(f"Tiempo total: {elapsed:.2f} s")
print(f"Tokens entrada: {data.get('prompt_eval_count', 'N/D')}")
print(f"Tokens salida: {data.get('eval_count', 'N/D')}")
print(f"Tokens totales estimados: {(data.get('prompt_eval_count') or 0) + (data.get('eval_count') or 0)}")
print(f"Duración evaluacion ns: {data.get('eval_duration', 'N/D')}")
