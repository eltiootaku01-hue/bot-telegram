# BOT-IA — Política operativa de control de comunidades

**Estado:** motor de política implementado en una rama aislada; integración con los adaptadores todavía pendiente.  
**Objetivo:** mantener Telegram y Discord separados, compartir la planificación y degradar de manera controlada con recursos limitados.

## 1. Límites que no se pueden romper

1. **Separación por plataforma:** cada evento se identifica por plataforma + ID del evento. Un mismo ID de Telegram y de Discord representa dos eventos diferentes. No se vinculan automáticamente las identidades de un mismo usuario.
2. **Permisos primero:** este controlador no concede acceso a grupos, servidores, canales, temas ni acciones administrativas. Cada adaptador debe conservar sus comprobaciones de autorización.
3. **Moderación antes de la admisión ordinaria:** aplicar validación barata de longitud/estructura y el filtro determinista de seguridad antes de someter el mensaje a cuotas ordinarias. Sólo un evento ya clasificado de manera confiable puede llegar con prioridad P0/P1; no se debe permitir que texto del usuario elija su propia prioridad.
4. **Un portavoz público por sala y turno:** adquirir una reserva de portavoz vinculada a plataforma + sala + task_id. Liberarla en un bloque de limpieza incluso si la ejecución falla. La reserva en memoria evita colisiones dentro de este proceso, no coordina múltiples procesos o PCs.
5. **Sin bucles de bots:** los eventos marcados como escritos por bots se rechazan. Los adaptadores deben comprobar la identidad real del emisor y evitar puentes automáticos Telegram ↔ Discord.
6. **Trabajo acotado:** colas por plataforma, límite por sala, límite pendiente por usuario, ventana de ritmo por usuario, deduplicación y caducidad del trabajo no esencial.
7. **Sin datos sensibles en métricas:** el snapshot sólo expone contadores y profundidades; no debe registrar tokens, contenido del mensaje, prompts ni secretos.
8. **Autoridad física intacta:** este motor no sustituye la autoridad física de WebChat, la exclusión mutua del navegador, ni los contratos existentes de TaskEngine o TaskScheduler.
9. **Sin garantías inventadas:** la existencia de un motor de política no demuestra que un adaptador lo esté llamando, que Discord esté conectado ni que 200 usuarios simultáneos hayan sido probados.

## 2. Perfiles de control

Los perfiles de esta tabla regulan la admisión de eventos y la longitud de cola. **No son el mando de RAM** y no significan que el proceso quede físicamente limitado a esa cantidad de memoria. El presupuesto RAM del Resource Governor sigue siendo una política complementaria.

| Límite | Medio (predeterminado) | Bajo en recursos |
|---|---:|---:|
| Cola máxima por plataforma | 256 eventos | 128 eventos |
| Reserva P0/P1 dentro de la cola | 32 | 24 |
| Capacidad ordinaria antes de usar la reserva | 224 | 104 |
| Máximo pendiente por sala | 80 | 32 |
| Máximo pendiente por usuario en una sala | 5 | 3 |
| Eventos ordinarios admitidos por usuario | 6 cada 10 segundos | 3 cada 10 segundos |
| Caducidad de P2/P3/P4 pendientes | 45 segundos | 20 segundos |
| Ventana de deduplicación | 15 minutos | 10 minutos |
| Claves de deduplicación retenidas como máximo | 10.000 | 5.000 |
| Recursos extra requeridos | Ninguno | Ninguno; biblioteca estándar de Python |

La política **Medio** usa valores conservadores para un escritorio local y es la opción predeterminada del motor aislado. El perfil **Bajo en recursos** reduce colas y trabajo acumulado para recuperarse antes. Ambos necesitan ajustarse con mediciones reales, no por intuición.

Los límites de tasa cuentan eventos ordinarios aceptados de ese usuario dentro de la ventana temporal. P0/P1 no entran en esa cuota, pero comparten una cola de tamaño máximo y por lo tanto no tienen capacidad ilimitada.

## 3. Orden de prioridad

| Nivel | Trabajo | Regla |
|---|---|---|
| **P0** | Moderación y seguridad | Primero. Requiere clasificación confiable antes de entrar al motor. No caduca por TTL. |
| **P1** | Acciones operativas críticas/autorizadas | Segundo. Autorización independiente obligatoria. No caduca por TTL. |
| **P2** | Conversación, preguntas dirigidas y tareas ordinarias | Se aplican cuotas de usuario/sala y el control de recursos. |
| **P3** | Minijuegos y actividad secundaria | Se suspende antes ante presión de recursos. Caduca en cola. |
| **P4** | Navegación pesada, matriz y trabajo de fondo | Se admite cuando exista capacidad y el Resource Governor lo permita. Caduca en cola. |

Una prioridad P0/P1 no autoriza a ignorar permisos, validación, privacidad, límites de la plataforma o una acción externa peligrosa. Es sólo orden de atención dentro del planificador.

Si una cola se llena de P0/P1, el motor no crece sin límite. Un evento crítico puede desplazar un evento de menor prioridad de **su misma plataforma**. Si no existe un candidato de menor prioridad, el controlador devuelve explícitamente el motivo critical_queue_full; el adaptador/panel debe alertar y registrar el estado sin incluir el contenido del mensaje.

## 4. Qué hace el motor implementado

Archivo: src/bot_ia/core/community_control.py.

- Normaliza plataforma, ID de evento, sala y usuario, y limita texto a 24.000 caracteres e identificadores externos a 256 caracteres.
- Mantiene colas separadas de Telegram y Discord en memoria.
- Rechaza autoría marcada como bot y duplicados por plataforma/ID de evento.
- Limita las admisiones ordinarias por usuario y sala.
- Reserva capacidad de cola para P0/P1; una entrada crítica puede desplazar trabajo menos prioritario de la misma plataforma y lo informa en el resultado.
- Despacha prioridad alta primero y reparte eventos de igual prioridad de forma rotativa por plataforma, sala y usuario.
- Caduca trabajo P2/P3/P4 anticuado; conserva P0/P1 hasta procesarlos o hasta que se alcance el límite acotado que produce una señal explícita de saturación.
- Proporciona una reserva temporal de portavoz por plataforma + sala, de 1 a 120 segundos (20 segundos por defecto).
- Ofrece métricas agregadas sin texto de mensaje ni credenciales.

### Qué no hace todavía

- No abre conexiones con Telegram ni Discord.
- No escribe en la outbox ni marca los eventos completados en el ledger.
- No persiste las colas entre reinicios; el evento admitido pero no procesado se pierde si cae el proceso. Por eso la outbox/ledger durables de cada adaptador continúan siendo obligatorios.
- No conecta automáticamente la política a TaskOrchestrator, ResourceGovernor o GUI.
- No suspende procesos de navegador que ya estén ejecutándose ni confirma el estado físico de WebChat.
- No prueba carga real ni ofrece una garantía de latencia.

## 5. Contrato de integración obligatorio

Antes de encolar un evento, el adaptador debe, en este orden:

1. Validar que el sobre del evento no está malformado y que el texto/metadatos están acotados.
2. Identificar y autorizar el destino y los permisos del usuario por la autoridad específica de la plataforma.
3. Ignorar eventos procedentes de bots y evitar cualquier bucle de puente.
4. Ejecutar la clasificación determinista de seguridad antes de las cuotas ordinarias. Si el mensaje desencadena una actuación de moderación, crear/encaminar la tarea P0; si requiere una acción administrativa crítica, P1 sólo después de autorizarla.
5. Reclamar el identificador de evento con el ledger durable que corresponda antes de efectos irreversibles. El motor de colas en memoria no reemplaza ese contrato.
6. Encolar sólo el trabajo necesario. No se inicia una llamada de IA por cada evento entrante ni se despiertan los seis personajes a la vez.
7. Al retirar una tarea P2/P3/P4, consultar el Resource Governor vigente; si la medición está ausente/obsoleta o el presupuesto no la admite, aplazar/rechazar la tarea ordinaria con un motivo explícito.
8. Antes de respuesta pública, adquirir la reserva de portavoz, volver a comprobar que la tarea sigue vigente y que el destino sigue autorizado. Liberar la reserva al finalizar y enviar mediante la outbox del mismo proveedor.
9. Respetar los tiempos de espera y límites de salida del proveedor. No realizar bucles de reintento inmediato tras un HTTP 429 o una desconexión.

Telegram debe conservar su ledger, outbox, router de salas/temas y comprobaciones de permisos actuales. Discord necesita un adaptador real de Gateway, intents mínimos, autorización de servidor/canal, identificación de mensajes, outbox y política de reconexión antes de ser marcado como operativo.

## 6. Control de carga

- **Normal:** procesar según prioridad y admitir P2/P3/P4 si la cola y el Resource Governor lo permiten.
- **Advertencia de RAM:** detener nuevas tareas P4 pesadas; mantener las rutas esenciales.
- **Presión alta:** detener P3 y limitar P2 según el Resource Governor.
- **Medición desconocida/obsoleta:** denegar las tareas secundarias que requieren autorización de recursos; nunca interpretar una medición ausente como cero.
- **Cola ordinaria al límite:** devolver motivos de rechazo observables; no crecer sin límite ni producir un aviso público por cada mensaje.
- **Cola crítica al límite:** mostrar un estado crítico explícito; no mentir diciendo que el evento se completó.
- **Reinicio del proceso:** la cola del controlador se pierde; la recuperación/relectura debe apoyarse en el ledger y la outbox durables del adaptador. No reenviar automáticamente efectos ambiguos.

El motor de comunidad regula cola/rendimiento; el Resource Governor regula admisión según memoria. Una política no sustituye a la otra.

## 7. Validación necesaria antes de habilitar tráfico real

1. Ejecutar los tests de unidad de tests/test_community_control.py en Windows y Ubuntu.
2. Integrar sólo después de verificar que Telegram sigue respetando autorización, deduplicación, outbox y prioridad de moderación.
3. Añadir y validar el adaptador Discord; comprobar reconexión, intents, permisos y límites de API.
4. Probar mensajes duplicados, contenido extenso, autores-bot, dos salas por plataforma y colisión entre personajes.
5. Simular 100 usuarios por plataforma a ritmos graduales y verificar profundidad de cola, eventos caducados, tasa de rechazo, P0/P1, latencia p95 y no duplicación de respuestas.
6. Probar inundación controlada, desconexión, reinicio y recuperación de tareas ambiguas. La saturación debe ser visible y deliberada.
7. Medir en el PC Windows la RAM real del producto y validar su relación con el Resource Governor.

**Estado de cierre:** motor de política aislado + pruebas escritas; no integrado en el camino activo de mensajes, no ejecutado en CI en esta rama y no validado con 100 usuarios reales o simulados. No abrir ni fusionar la rama hasta completar esos gates por separado.
