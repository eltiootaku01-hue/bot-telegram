# BOT-IA

BOT-IA es un Knowledge Engine personal con un mismo backend para uso normal,
Telegram y una API HTTP compatible con GPT Actions. La evidencia, memoria,
reglas, routing y gestión de providers no dependen de una interfaz concreta.

## Uso normal en Windows

Para usar BOT-IA como usuario final, utiliza `BOT-IA.exe` o el acceso directo del escritorio.

En la primera ejecución aparece un asistente gráfico para:

1. Elegir la biblioteca de ONE NEKO PUNCH.
2. Seleccionar el proveedor IA.
3. Introducir la clave del proveedor cuando sea necesaria.
4. Configurar Telegram de forma opcional.

**Ollama local** ya es una opción de primera clase: no pide una clave API remota y comprueba `http://127.0.0.1:11434` solo al guardar la configuración. BOT-IA no inicia Ollama automáticamente y el adapter usa `keep_alive=0` para que el modelo no quede residente después de una petición.

Después de guardar, BOT-IA se abre directamente en su interfaz gráfica. No necesitas instalar Python ni ejecutar PowerShell para el uso normal.

El paquete incluye `BOT-IA-Setup.exe`, `BOT-IA.exe` y `BOT-IA-Core.exe`. Las instrucciones completas están en `docs/INSTALACION_WINDOWS.md`.

## Interfaces de desarrollo

### Consola

Para desarrollo o diagnóstico:

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode console
```

También, después de instalar el proyecto:

```powershell
bot-ia --mode console
```

El proveedor por defecto es OpenAI. Puede cambiarse con `BOT_IA_PROVIDER`.

### Telegram

Configura `TELEGRAM_BOT_TOKEN` en `.env` o como variable de entorno y ejecuta:

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode telegram
```

El cliente usa long polling, controla offsets y reintentos, evita perder un
update cuando falla la entrega de su respuesta y divide respuestas largas para
respetar el límite de Telegram. Cada mensaje pasa por el mismo `BotApplication`
que usa la consola y la API web.

### API web / ChatGPT Actions

Inicia la API JSON:

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode web --host 127.0.0.1 --port 8787
```

Endpoints:

- `GET /health`
- `GET /openapi.json`
- `POST /v1/query`

La API local no queda expuesta públicamente por defecto. Para una integración externa se necesita HTTPS público y el token correspondiente.

### Chat web móvil

Para tener una interfaz tipo chat directamente en el navegador, sin Node, Flask,
React, base de datos adicional ni proceso frontend separado:

```powershell
$env:PYTHONPATH = "src"
python -m bot_ia --mode web-chat --host 127.0.0.1 --port 8787
```

Abre `http://127.0.0.1:8787/`. La interfaz es responsive y conserva el historial visible en `localStorage`; las consultas siguen pasando por `BotApplication`, la biblioteca, memoria, EvidenceGate y el provider seleccionado.

Para usarla desde un teléfono en una LAN de confianza, configura un token de al menos 32 caracteres, usa un host privado/LAN y habilita explícitamente `BOT_IA_ALLOW_INSECURE_LAN=true`. Para acceso fuera de la LAN se debe mantener HTTPS. No se recomienda exponer el puerto directamente a Internet.

## Providers

OpenAI, Groq y OpenRouter siguen disponibles para las rutas remotas. Ollama está habilitado como capacidad local ligera, pero **no es un servicio residente**: solo se utiliza cuando `BOT_IA_PROVIDER=ollama` y Ollama está disponible.

El modelo experimental recomendado es `qwen3:1.7b-q4_K_M`. Ollama publica esa variante oficial en torno a 1.4 GB; el rendimiento real en el Ryzen 5 5600G debe medirse en el equipo objetivo antes de promoverlo como cerebro único. citeturn1search4turn1search0

No existe una puerta trasera legítima que permita saltarse autenticación de proveedores remotos. La ruta API-free que estamos adoptando es inferencia local mediante Ollama en localhost; el endpoint local no requiere una clave remota. Ollama documenta además tool calling para modelos compatibles como Qwen3. citeturn3search9turn3search6

## Biblioteca, evidencia y memoria

La recuperación factual local se realiza antes de recurrir a generación externa cuando la consulta puede resolverse con evidencia de la biblioteca. EvidenceGate impide presentar como hechos las suposiciones del modelo y mantiene separadas evidencia, inferencia y propuesta.

La memoria persistente es local y no modifica automáticamente el canon del proyecto.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

La CI comprueba Linux y Windows, compila la superficie de código e importa el runtime y el lanzador.

## Seguridad de secretos

El archivo `.env` real se mantiene local y está excluido del control de versiones. Nunca pongas claves reales en archivos versionados.
