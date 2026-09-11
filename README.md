# BOT-IA

BOT-IA es un Knowledge Engine personal con un mismo backend para uso normal,
Telegram y una API HTTP compatible con GPT Actions. La evidencia, memoria,
reglas, routing y gestión de providers no dependen de una interfaz concreta.

## Uso normal en Windows

Para usar BOT-IA como usuario final, utiliza `BOT-IA.exe` o el acceso directo del escritorio.

En la primera ejecución aparece un asistente gráfico para:

1. Elegir la biblioteca de ONE NEKO PUNCH.
2. Seleccionar el proveedor IA.
3. Introducir la clave del proveedor.
4. Configurar Telegram de forma opcional.

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

La API local no queda expuesta públicamente por defecto. Para una integración externa se necesita HTTPS público y el token correspondiente.

## Providers

OpenAI y Groq están habilitados en la configuración base; OpenRouter está disponible como fallback configurable y Coze queda disponible cuando se aportan sus credenciales. Se admite más de una cuenta por provider.

Ollama permanece desactivado por defecto y limitado al perfil local ligero documentado para uso puntual.

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
