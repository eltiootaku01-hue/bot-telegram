# Investigación de workflows de bots de Telegram

Fecha: 2026-09-20

## Objetivo

Comparar cómo proyectos de bots de Telegram resuelven cuatro clases de trabajo que este proyecto necesita:

- recepción de nuevos integrantes y anti-bot;
- moderación y tareas diferidas;
- recepción y procesamiento de álbumes/media;
- trabajo operativo con colas, estados y recuperación.

La conclusión de esta investigación se usa como criterio de diseño del proyecto, no como dependencia de código externo.

## Fuentes principales

### Telegram Bot API

https://core.telegram.org/bots/api

La API oficial confirma que `chat_member` requiere que el bot sea administrador y que el tipo esté habilitado en `allowed_updates`. También existe `chat_join_request` para flujos basados en solicitudes de ingreso. Para expulsar/reintegrar, Telegram expone `banChatMember` y `unbanChatMember`; para contener temporalmente a un miembro de un supergrupo existe `restrictChatMember` con el permiso administrativo correspondiente.

Decisión para Chie:

1. observar `chat_member`;
2. restringir al nuevo miembro antes de habilitarlo;
3. presentar una verificación explícita;
4. si responde `No soy un bot`, restaurar permisos;
5. si responde `Sí, soy un bot`, expulsar y desbanear para permitir un nuevo intento;
6. si vence el TTL, ejecutar la misma expulsión mediante una tarea durable.

### Rose Bot

https://github.com/msgpc/rose-bot

Rose combina captcha, anti-flood, mensajes de bienvenida/despedida, filtros y herramientas administrativas. El proyecto describe el captcha como una forma de filtrar entradas automáticas y considera la protección una capa separada de la administración cotidiana.

Patrón adoptado:

- separación entre recepción y seguridad;
- acciones automáticas pequeñas;
- filtros específicos en vez de intentar resolver todo con IA.

Patrón evitado:

- convertir cada interacción social en una decisión generativa.

### telegram-antispam-bot

https://github.com/NikitaUshakov/telegram-antispam-bot

Su README describe un flujo de mute inmediato, captcha de un toque, expulsión por respuesta incorrecta o timeout y una política de flood basada en una ventana temporal. También destaca la separación entre lógica pura y handlers de Telegram.

Patrones adoptados:

- lógica de decisión separada de llamadas Telegram;
- timeout configurable;
- estado persistente;
- pruebas de la lógica sin red.

Mejora respecto del ejemplo:

- este proyecto usa SQLite durable y estados de expiración para sobrevivir reinicios;
- la decisión está protegida con una transición SQL condicionada por usuario, estado y expiración.

### tg-moderation-bot

https://github.com/Danik105/tg-moderation-bot

El proyecto documenta TTL para captcha e historial anti-spam, limpieza periódica para evitar crecimiento sin límite y una cola de tareas para acciones diferidas.

Patrones adoptados:

- TTL explícito;
- limpieza periódica;
- colas durables para trabajo diferido;
- errores de Telegram tratados como estados operativos.

### Telegram-Moderation-Bot

https://github.com/Heng-zm/Telegram-Moderation-Bot

Este proyecto usa una cola persistente de tareas para expiración de captcha, expiración de mute y eliminación diferida. Su README explica que la persistencia permite reanudar acciones pendientes después de un reinicio y limpiar tareas terminadas/canceladas.

Este patrón coincide con la decisión de no usar únicamente `asyncio.sleep()` para seguridad de miembros.

### aiogram MediaGroupAggregatorMiddleware

https://github.com/aiogram/aiogram/pull/1777

La discusión de aiogram recuerda un detalle importante: Telegram entrega cada elemento de un álbum como una actualización independiente. La propuesta de `MediaGroupAggregatorMiddleware` usa una ventana de agregación y discute explícitamente los riesgos de concurrencia y de responder demasiado pronto cuando se necesita conservar la semántica de reintento.

Decisión para Cami:

- agrupar por `media_group_id`;
- persistir cada asset individualmente;
- usar una identidad durable para el álbum;
- mostrar una sola acción de etiquetado por conjunto;
- mantener cada asset como unidad publicable/reintentable.

## Método operativo adoptado por este proyecto

Cada trabajo importante debe seguir esta tubería:

```
entrada Telegram
   ↓
validación de acceso
   ↓
clasificación del trabajo
   ↓
estado durable
   ↓
claim/idempotencia
   ↓
acción Telegram o procesamiento local
   ↓
persistencia del resultado
   ↓
observación agregada
   ↓
recuperación si la entrega es ambigua
```

No se permite saltar directamente de "mensaje recibido" a "IA generativa" para trabajos que puedan resolverse con código determinista.

## Asignación funcional actual

### Cari

- anfitriona del Café Otaku;
- conversación comunitaria;
- trivia de anime;
- recomendaciones y eventos cotidianos;
- moderación ligera cuando corresponde.

### Sunna

- WaifuMon;
- gacha;
- encuentros;
- colección;
- evolución/fusión;
- combate;
- progresión y puntos asociados.

### Cami

- archivo;
- catálogo;
- recepción de media;
- álbumes;
- clasificación;
- publicación;
- pedidos en ejecución;
- misterio diario.

### Chie

- configuración de comunidad;
- bienvenida;
- despedida;
- verificación humana;
- permisos;
- avisos;
- coordinación;
- revisión de Ciudad Animals.

## Anti-bot de Chie

El flujo elegido deliberadamente no trata el botón como una adivinanza irrelevante. Es un control explícito de incorporación:

```
nuevo miembro
   ↓
restringir envío
   ↓
¿Sos un bot?
   ├─ No → verificar → restaurar permisos
   ├─ Sí → expulsar → desbanear → permitir reingreso
   └─ timeout → expulsar → desbanear
```

El estado vive en `human_verifications`.

Estados relevantes:

- `pending`
- `expiring`
- `verified`
- `rejected`
- `expired`

Las transiciones de decisión y expiración son condicionales y no dependen de que una sola instancia del bot permanezca viva.

## Cami: método avanzado para trabajo con media

El sistema usa una mesa de trabajo en vez de una simple secuencia de handlers:

```
ingreso
 → deduplicación
 → álbum si corresponde
 → etiquetado
 → destino
 → programación
 → claim
 → publicación
 → confirmación de IDs
 → reconciliación de entrega
```

El workboard de Cami ordena solicitudes y media por riesgo y urgencia. Las entregas ambiguas quedan como `delivery_unknown` para decisión humana antes de reintentar, evitando asumir que Telegram falló solo porque la escritura local no quedó registrada.

## Qué no se adopta

No se adopta:

- memoria global en RAM para estados importantes;
- `sleep` como única fuente de verdad para expiraciones;
- llamadas LLM para reglas que son deterministas;
- una única cola que mezcle seguridad, juegos y publicaciones sin tipos;
- publicación de media sin claim previo;
- interpretación de una respuesta humana por parte de IA cuando un botón puede expresar la decisión exactamente.

## Resultado

La evolución de la plataforma debe ampliar estos mismos contratos:

- estado durable;
- actor y permisos explícitos;
- claim idempotente;
- separación lógica/Telegram;
- recuperación post-reinicio;
- observabilidad agregada;
- IA solamente como curadora o escalamiento cuando el problema no sea determinista.

Las nuevas funciones deben entrar primero en `app/`, sus regresiones en `tests/`, la documentación en `docs/` y solo la línea experimental vigente en `experiments/local_first/`.
