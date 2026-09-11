# Incidente de runtime — 2026-09-11

## Hallazgos

La auditoría del último commit detectó dos fallos reales que las pruebas anteriores no cubrían:

1. La GUI ejecutaba `application.handle(...)` en un hilo secundario y después llamaba `root.after(...)` desde ese hilo. Tkinter no debe recibir llamadas de UI desde hilos de trabajo; esto podía dejar al usuario viendo su mensaje sin recibir la respuesta.
2. El botón `Iniciar en Telegram` usaba `sys.executable --mode telegram` cuando estaba congelado como `BOT-IA-Core.exe`. Ese ejecutable es la GUI, no `bot_ia.__main__`, por lo que el argumento no iniciaba el poller de Telegram.

## Corrección

`desktop_entry.py` pasa a ser el punto de entrada del Core empaquetado. Mantiene el núcleo de BOT-IA intacto y añade sólo una capa de ejecución:

- las respuestas de trabajadores se colocan en una cola;
- el hilo principal de Tkinter vacía esa cola mediante `after()`;
- Telegram usa un proceso trabajador explícito con `--telegram-worker`;
- el trabajador valida `getMe`, ejecuta polling y escribe `work/telegram.log`;
- el botón de Telegram muestra si el proceso está activo o terminó con error.

## Prueba de regresión

Se añadió un smoke test que construye el runtime real y comprueba que una consulta local (`hola`) produce una respuesta sin API remota. También se añadieron pruebas estáticas del nuevo entrypoint.

## Ollama

Se dejó un experimento aislado en `experimental/ollama/`. El adaptador Ollama ya existente no exige API key para el endpoint local y usa `keep_alive = 0`. La prueba usa `qwen3:1.7b` y mide respuesta/latencia de generación. No se activa todavía como proveedor predeterminado hasta medirlo en el PC real.
