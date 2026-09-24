# BOT-IA Desktop / Café Otaku

BOT-IA usa una interfaz gráfica Qt Dark Cozy llamada **Café Otaku**, construida sobre
el mismo runtime que la consola, Telegram y la API HTTP.

## Uso normal

Para el usuario final, el punto de entrada sigue siendo `BOT-IA.exe`. En la
instalación nueva aparece el asistente de configuración y después el lanzador
abre `BOT-IA-Core.exe`, que ahora presenta la interfaz Qt de Café Otaku.

En desarrollo también puedes ejecutar:

```powershell
$env:PYTHONPATH = "src"
python -m gui.app
```

## Qué incluye Café Otaku

- Sidebar de Cari, Cami, Sunna, Chie, Chloe y Scarlet.
- Estado de la Taberna consultado desde SQLite cuando el personaje existe en el
  registro real de meseras.
- Chat general mediante `BotApplication` fuera del hilo de la GUI.
- Chat de Taberna mediante `WaitressSessionManager`, persistencia de
  `last_ticket_at` y `WebChatQueueManager`.
- Chat individual WebQueue para personajes que no están registrados como meseras.
- Píldoras para inventario/cartas, estado de descanso, chocolatada y duelo.
- Panel de operaciones para proyectos, Telegram, providers y estado de WebQueue.
- Navegador integrado `QWebEngineView` para la superficie controlada por
  `WebChatQueueManager`.
- Estado discreto de backend, outbox y WebQueue en el footer.
- Errores técnicos fuera de la interfaz; los detalles se registran en
  `work/gui.log`.

## Límites explícitos

El backend actual no contiene una API para crear grupos de Telegram, nombrar bots
como administradores ni mapear X/Twitter hacia topics de Telegram. Café Otaku no
simula esas capacidades: el panel informa de su ausencia en lugar de mostrar
botones que aparenten hacer algo que el backend no puede ejecutar.

El backend actual de Taberna tampoco define una economía de gacha/póker separada.
La píldora correspondiente usa la operación de duelo existente y deja claro que
no se ha inventado una mecánica adicional.

El registro SQLite actual contiene a Cari, Luna, Scarlet, Chloe y Mama Mia. Cami,
Sunna y Chie se muestran como personajes WebQueue cuando no existe una fila real
para ellas; la UI no fabrica estados SQLite.

## Seguridad y ciclo de vida

La GUI no crea un segundo cerebro ni una segunda base de conocimiento. Utiliza
`BotApplication`, por lo que conserva las mismas reglas de evidencia, routing,
memoria y providers.

Los mensajes generales se procesan en un pool Qt para que una llamada remota no
bloquee la interfaz. El WebQueue mantiene su QThread, timeouts, circuit breaker y
MutationObserver existentes.

Al cerrar la ventana, se detienen Telegram y Taberna, se cancela el WebQueue de
forma ordenada y se cierran las conexiones persistentes antes de terminar el
proceso.

## Paquete Windows

El proyecto genera:

- `BOT-IA.exe`: lanzador y asistente de primera configuración.
- `BOT-IA-Core.exe`: interfaz principal Café Otaku y runtime.
- `BOT-IA-Setup.exe`: instalador de Windows.

El build instala PySide6 y `tzdata` y realiza un smoke test del Core antes de
construir el instalador.

## Tests

La CI compila, ejecuta las comprobaciones de política, importa `gui.app` y
ejecuta la suite de unittest en Ubuntu y Windows con:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
