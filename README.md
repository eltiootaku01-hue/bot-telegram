# BOT-IA

BOT-IA es un Knowledge Engine personal con un mismo backend para uso normal,
Telegram y una API HTTP compatible con GPT Actions. La evidencia, memoria,
reglas, routing y gestión de providers no dependen de una interfaz concreta.

## Interfaces

### Uso normal

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode console
```

También, después de instalar el proyecto:

```powershell
bot-ia --mode console
```

### Telegram

Configura `TELEGRAM_BOT_TOKEN` como variable de entorno y ejecuta:

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode telegram
```

El cliente usa long polling, controla offsets, reintentos y errores de
transporte, y pasa cada mensaje por el mismo `BotApplication` que usa la
consola y la API web.

### API web / ChatGPT

Inicia una API local:

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode web --host 127.0.0.1 --port 8787
```

Endpoints:

- `GET /health`
- `GET /openapi.json`
- `POST /v1/query`

Ejemplo:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8787/v1/query" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"¿Quién es Kuro?","user_id":"local","conversation_id":"demo"}'
```

Para exponer la API fuera de la máquina se debe configurar una URL HTTPS
pública y `BOT_IA_API_TOKEN`. El runtime rechaza arrancar la API en una
interfaz no local si no existe ese token.

Variables relevantes:

```text
BOT_IA_ONE_NEKO_PUNCH_ROOT   Ruta externa al conocimiento de One Neko Punch
BOT_IA_UNIVERSE              Universo por defecto
BOT_IA_PROVIDER              Provider por defecto (ollama, gemini, openai...)
BOT_IA_API_TOKEN              Token Bearer de la API web
BOT_IA_PUBLIC_BASE_URL        URL HTTPS pública usada en /openapi.json
BOT_IA_HOST                   Host de la API web
BOT_IA_PORT                   Puerto de la API web
TELEGRAM_BOT_TOKEN            Token del bot de Telegram
```

`GET /openapi.json` genera el esquema OpenAPI que puede importarse en una
acción de un GPT. ChatGPT requiere que la API sea accesible mediante una URL
pública y HTTPS para ese uso; la API local por sí sola no convierte BOT-IA en
una función interna de ChatGPT.

## Providers

Los providers se configuran en `config/runtime.toml`. Las credenciales se
leen exclusivamente desde variables de entorno y nunca deben guardarse en el
repositorio. Se soportan providers locales y remotos mediante el
`ProviderManager`, con cuentas, fallback, cooldown y control de errores.

## Conocimiento y seguridad

El universo `one_neko_punch` se carga desde una ruta externa mediante
`BOT_IA_ONE_NEKO_PUNCH_ROOT`. El repositorio no contiene una ruta personal de
la máquina.

Las respuestas factuales pasan por `EvidenceGate`. Si la evidencia no es
suficiente, BOT-IA no debe convertir una suposición del modelo en un hecho.
Las reglas críticas se incorporan al contexto y fallan de forma cerrada si no
pueden conservarse dentro del presupuesto.

La memoria persistente es SQLite local, requiere autorización explícita y no
modifica automáticamente el canon.

## Pruebas

La suite completa se ejecuta sin credenciales ni servicios externos:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
