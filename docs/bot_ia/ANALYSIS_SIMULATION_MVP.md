# BOT-IA — Manual operativo de análisis y simulación

Este manual cubre la primera entrega del MVP por Telegram. Los comandos y ejemplos siguientes son procedimientos para ejecutar en el PC propietario; no implican que se haya realizado una conexión real desde CI.

## 1. Preparación en Windows

### Requisitos

- Windows 10/11 de 64 bits.
- Python **3.14**, que es la versión utilizada por el workflow de CI. Durante la instalación, marca **Add Python to PATH**.
- Git para obtener el repositorio.
- Un bot de Telegram creado con BotFather y su token.
- Una clave de un proveedor IA habilitado en `config/runtime.toml` para usar `/analizar`. `/simular` no necesita clave ni conexión a proveedores.
- Conexión a Internet solo para la operación real de Telegram y el proveedor remoto.

Abre PowerShell en el directorio del repositorio:

```powershell
python --version
git status --short
python -m pip install --upgrade pip
python -m pip install -e .
```

La instalación editable usa las dependencias declaradas en `pyproject.toml`. Para ejecutar las pruebas automatizadas instala además pytest:

```powershell
python -m pip install pytest
```

No necesitas instalar Chromium para el modo Telegram ni para la simulación. No inicies varias instancias de BOT-IA con el mismo token.

### Archivo `.env`

Crea el archivo `.env` en la **raíz del repositorio**, al mismo nivel que `pyproject.toml`. El programa lo carga antes de interpretar el modo. Una variable ya definida en el entorno de Windows tiene prioridad sobre la del archivo.

Plantilla: sustituye los valores de ejemplo por tus propios valores locales. No copies los textos de ejemplo como si fueran credenciales válidas.

```dotenv
TELEGRAM_BOT_TOKEN=REEMPLAZAR_CON_TOKEN_REAL
BOT_IA_PROVIDER=openai
OPENAI_API_KEY=REEMPLAZAR_CON_CLAVE_REAL

# Opcional: habilita un fallback si ese proveedor está habilitado en runtime.toml.
GROQ_API_KEY=
OPENROUTER_API_KEY=

# Opcionales: raíces locales de bibliotecas. Usa rutas absolutas.
BOT_IA_ONE_NEKO_PUNCH_ROOT=C:\ruta\a\biblioteca\one_neko_punch
BOT_IA_NEKO_FISH_ONLINE_ROOT=C:\ruta\a\biblioteca\neko_fish_online
BOT_IA_NEKO_OF_THE_DEAD_ROOT=C:\ruta\a\biblioteca\neko_of_the_dead
BOT_IA_MY_NEKO_ACADEMIA_ROOT=C:\ruta\a\biblioteca\my_neko_academia
BOT_IA_ATTACK_ON_NEKO_ROOT=C:\ruta\a\biblioteca\attack_on_neko
```

Reglas de seguridad:

- **Nunca guardes tokens o claves reales en Git.** `.env` es local; comprueba `git status --short` antes de cualquier commit y no fuerces su inclusión.
- No publiques el token de Telegram en capturas, logs, chats ni incidencias.
- El token de Telegram y las claves IA son secretos distintos.
- Si una clave se expuso, revócala en el proveedor y genera otra.

### Qué proveedores están habilitados

Abre `config/runtime.toml` en un editor de texto y revisa los bloques `[providers.<id>]`, en especial `enabled`, `model`, `fallback` y `accounts.*.secret_env`.

En el perfil base del repositorio:

| Proveedor | Estado inicial | Variable de credencial |
|---|---|---|
| OpenAI | Habilitado | `OPENAI_API_KEY` |
| Groq | Habilitado | `GROQ_API_KEY` |
| OpenRouter | Habilitado | `OPENROUTER_API_KEY` |
| Coze | Deshabilitado | `COZE_API_TOKEN` |
| Ollama | Deshabilitado | Sin clave remota; requiere activación local explícita |

La cadena configurada por defecto es OpenAI → Groq → OpenRouter; los fallbacks solo sirven si el proveedor está habilitado y tiene una cuenta utilizable. Selecciona el proveedor principal con `BOT_IA_PROVIDER`. No habilites proveedores editando el archivo sin revisar antes sus requisitos y modelo.

Para Ollama, no basta con instalarlo: la configuración base lo deja deshabilitado. Su activación requiere seleccionar `BOT_IA_PROVIDER=ollama` y declarar explícitamente `BOT_IA_ENABLE_LOCAL_OLLAMA=true`, además de instalar y preparar el modelo local.

## 2. Preflight de configuración

Desde la raíz del repositorio ejecuta:

```powershell
python -m bot_ia --mode preflight
$LASTEXITCODE
```

El comando emite un único informe JSON de diagnóstico. No inicia Telegram, no llama al proveedor, no comprueba la autenticación real de ninguna clave y no crea el runtime ni abre su base de datos.

Comprueba:

- Que `config/runtime.toml` exista y pueda cargarse.
- Qué proveedor se seleccionó y si su cadena de fallback tiene una credencial declarada presente.
- Si existe `TELEGRAM_BOT_TOKEN`, sin imprimir su valor. La autenticación de Telegram queda como `NOT_CHECKED`.
- Si las cinco raíces de biblioteca son accesibles y si el inventario pudo examinarse dentro de los límites configurados.

Códigos de salida:

| Código | Significado | Acción |
|---:|---|---|
| `0` | Configuración cargable; puede ser `READY` o `WARNING`. | Lee `overall_status`, `diagnostics` y cada raíz. Un warning no demuestra conectividad. |
| `2` | La cadena del proveedor seleccionado no tiene credenciales configuradas utilizables. | Comprueba `BOT_IA_PROVIDER`, `enabled`, `fallback`, `secret_env` y la variable correspondiente en `.env`. |
| `3` | Falta o es inválida la configuración runtime. | Comprueba que estés en la raíz del repositorio y que `config/runtime.toml` sea TOML válido. No pegues secretos en ese archivo. |

Una variable presente solo prueba que hay un valor configurado; **no prueba que la clave sea válida**, que la cuenta tenga saldo/permisos, ni que el endpoint responda.

Si una raíz aparece como `NOT_ACCESSIBLE`, `TIMEOUT`, `LIMIT_EXCEEDED` o `UNREADABLE`, corrige la ruta, los permisos o el tamaño/cantidad de archivos según corresponda. Usa rutas absolutas existentes. Las raíces faltantes pueden dejar el informe en `WARNING`; la simulación local no depende de ellas, pero el análisis no debe afirmar que recuperó evidencia documental si no la recuperó.

## 3. Arrancar y detener Telegram

Después de revisar el preflight y comprobar que el token es el correcto:

```powershell
python -m bot_ia --mode telegram
```

Al arrancar, el programa realiza una comprobación real de Telegram (`getMe`) y después inicia el poller. Esta es una operación de red; no forma parte del preflight ni de la CI focalizada.

- Deja abierta esa ventana de PowerShell mientras el bot esté activo.
- Para detenerlo de forma normal, pulsa **Ctrl+C** y espera a que el proceso finalice.
- No lances otro proceso con el mismo token. El runtime usa un lock de instancia para impedir pollers concurrentes con ese token.
- No borres locks mientras una instancia siga ejecutándose.
- Si aparece un error de token/configuración, detén el proceso, corrige `.env` y vuelve a ejecutar preflight. No compartas el token para pedir ayuda.

El modo Telegram necesita `TELEGRAM_BOT_TOKEN`. Para que `/analizar` funcione necesita además un proveedor seleccionado con credenciales válidas y conectividad. `/simular` es local y determinista.

## 4. Prueba funcional de `/simular`

Envía este comando al bot en Telegram:

```text
/simular {"base":{"ventas":100},"scenarios":[{"name":"crecimiento","changes":[{"metric":"ventas","operation":"add","value":20}]}]}
```

Criterio de aceptación: la respuesta debe indicar una simulación válida del escenario `crecimiento`, con `ventas` pasando de **100 a 120**, diferencia absoluta **20** y variación porcentual **20 %**. La simulación no debe requerir una clave IA ni llamar a un proveedor externo.

Si la entrada es inválida, el comando debe responder con un estado controlado de simulación inválida y no publicar resultados parciales. Si no se obtiene 120, conserva el texto del comando y la respuesta sin incluir secretos y ejecuta el gate focalizado descrito en la sección 7.

## 5. Prueba funcional de `/analizar`

Con Telegram activo y un proveedor habilitado, envía una petición con contenido concreto, por ejemplo:

```text
/analizar Evalúa si conviene ampliar el horario de una cafetería de 8 a 10 horas diarias durante un mes. Considera costes, demanda, riesgos y cómo medir el resultado.
```

La respuesta aceptada debe presentar un análisis estructurado con:

- `objective`: objetivo del análisis.
- `assumptions`: supuestos explícitos.
- `unknowns`: datos faltantes.
- `alternatives`: alternativas consideradas.
- `risks`: riesgos relevantes.
- `recommendation`: recomendación razonada.
- `next_action`: siguiente acción concreta.
- `limitations`: límites del análisis.

El resultado debe indicar qué contenido se analizó y separar ese contenido de la evidencia documental recuperada. El texto escrito por el usuario no es evidencia verificada. Si no se recuperaron documentos de una biblioteca, la respuesta debe decirlo y no inventar referencias, fuentes o identificadores.

Esta prueba requiere un proveedor real. Si la clave está presente pero la autenticación falla, el proveedor no responde o devuelve una salida que no cumple el esquema, BOT-IA debe devolver un error/estado controlado y no presentar el análisis como completado. Revisa el estado, el mensaje controlado y la configuración; nunca copies la clave en el informe de diagnóstico.

## 6. Diagnóstico rápido

| Síntoma | Comprobación | Acción recomendada | Evidencia de resolución |
|---|---|---|---|
| Preflight devuelve código 3 | Ruta actual y `config/runtime.toml` | Volver a la raíz del repo y corregir el TOML | Preflight termina con 0 o 2 y muestra configuración `VALID` |
| Preflight devuelve código 2 | Proveedor seleccionado, `enabled`, fallback y nombre `secret_env` | Definir una credencial válida para un proveedor habilitado de la cadena | Preflight ya no reporta la cadena sin credenciales; esto no prueba autenticación |
| Token de Telegram ausente | `TELEGRAM_BOT_TOKEN` en `.env` o entorno | Definir el token local y volver a ejecutar preflight | Informe indica `token_present: true`; la autenticación sigue sin comprobarse |
| Raíz de biblioteca inaccesible | Variable de raíz, existencia y permisos de carpeta | Corregir la ruta absoluta o permisos | Informe muestra directorio accesible e inventario `OK` |
| Telegram falla al arrancar | Token vigente, red y respuesta de `getMe` | Verificar token con BotFather y conectividad; no exponerlo | El proceso supera el chequeo inicial y permanece en polling |
| `/simular` no devuelve ventas 120 | JSON enviado y respuesta completa | Repetir el ejemplo literal y correr el gate focalizado | Test determinista pasa y respuesta del comando reporta 100 → 120 |
| `/analizar` no se completa | Proveedor habilitado, credencial y conectividad | Revisar el error controlado y probar una clave válida | Test con proveedor falso pasa; después una prueba real devuelve esquema válido sin inventar evidencia |

## 7. Validación automatizada del MVP

Desde la raíz del repositorio, con el entorno del proyecto instalado:

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_analysis_simulation_mvp.py tests/test_runtime_preflight.py tests/test_telegram_analysis_simulation_integration.py
```

Ese es el mismo conjunto del job **BOT-IA MVP focused tests** en CI. Incluye simulación determinista, análisis con proveedor falso, preflight y comandos a través de Telegram con transporte HTTP controlado. Las pruebas no necesitan token real ni hacen llamadas a Telegram o proveedores externos.

El gate remoto corre en Ubuntu y Windows con límite de 120 segundos para el paso de tests. Un resultado verde prueba el conjunto automatizado en esos entornos, no la validez de las credenciales del propietario ni una sesión real de Telegram.

## 8. Qué queda como prueba real del propietario

**TARGET-MACHINE SMOKE TEST: NOT EXECUTED** en este entorno. No se dispone aquí del PC ni de las credenciales reales, así que no se afirma que el bot haya iniciado sesión en Telegram o que un proveedor real haya completado `/analizar`.

Cuando estés en tu PC, la secuencia concreta es:

1. Crear el `.env` local sin añadirlo a Git.
2. Ejecutar `python -m bot_ia --mode preflight` y revisar el JSON y el código de salida.
3. Ejecutar `python -m bot_ia --mode telegram` y confirmar que supera `getMe`.
4. Enviar el ejemplo de `/simular` y comprobar ventas 100 → 120.
5. Enviar el ejemplo de `/analizar`; verificar el esquema, el manejo de errores y que no se inventen referencias documentales.
6. Detener con Ctrl+C. Registrar solo estados y errores saneados; nunca registrar tokens ni claves.

La aceptación en CI y la prueba real del PC son evidencias distintas. No marques el MVP como operativo para el propietario hasta terminar esa secuencia.
