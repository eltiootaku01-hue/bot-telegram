# Usar BOT-IA desde ChatGPT web

BOT-IA expone `GET /openapi.json` para integrarse como una API externa mediante
GPT Actions. La acción usa el mismo `BotApplication`, por lo que ChatGPT no
recibe un segundo sistema de conocimiento: consulta el runtime de BOT-IA.

## 1. Ejecutar la API

En la máquina que contiene el conocimiento, configura `.env` (usa
`.env.example` como plantilla) o las variables de entorno. Como mínimo:

```text
BOT_IA_ONE_NEKO_PUNCH_ROOT=C:\ruta\a\one-neko-punch
BOT_IA_PROVIDER=openai
OPENAI_API_KEY=tu-clave-real
BOT_IA_API_TOKEN=un-token-largo-y-aleatorio
BOT_IA_PUBLIC_BASE_URL=https://tu-dominio.example
```

Groq y Coze son proveedores adicionales configurables. Coze requiere además
`COZE_API_TOKEN` y `COZE_BOT_ID` cuando se habilita en `runtime.toml`.

Después:

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode web --host 127.0.0.1 --port 8787
```

Para ChatGPT la API debe ser accesible desde Internet mediante una URL HTTPS.
No se debe publicar la API sin `BOT_IA_API_TOKEN`.

El endpoint del esquema será:

```text
https://tu-dominio.example/openapi.json
```

## 2. Configurar la acción

En un GPT que permita acciones, crea una acción nueva e importa el esquema
OpenAPI desde `/openapi.json`. La autenticación de la acción debe ser una
clave Bearer cuyo valor sea el mismo `BOT_IA_API_TOKEN` configurado en el
servidor.

La operación principal es `queryBotIA` y llama a:

```text
POST /v1/query
```

con un cuerpo como:

```json
{
  "message": "¿Qué ocurrió en el capítulo 4?",
  "user_id": "chatgpt-user",
  "conversation_id": "chatgpt-session"
}
```

## 3. Responsabilidad de cada lado

ChatGPT interpreta la conversación y decide cuándo usar la acción.
BOT-IA se encarga del universo, recuperación, evidencia, memoria, reglas,
routing, agentes y provider.

La acción no sustituye el control anti-invención de BOT-IA. Una respuesta
factual debe seguir pasando por `EvidenceGate` y el contrato de salida.

## 4. Providers

El runtime está preparado para varias cuentas/API keys de OpenAI, además de
Groq y Coze. La cadena configurada por defecto es OpenAI → Groq → Coze; Coze
está desactivado hasta que se configure su token y bot. Ollama no es necesario
para usar BOT-IA y está desactivado para no consumir recursos; si se habilita,
la configuración prevista es `qwen3:1b`.

## 5. Importante sobre ChatGPT

La integración no convierte una API local en una herramienta interna de
ChatGPT. ChatGPT necesita poder alcanzar el endpoint por Internet y el GPT
debe tener habilitadas las acciones. La disponibilidad para crear o editar
GPTs depende de la cuenta y del espacio de trabajo.
