# Manual operativo de Telegram — Bot Manager

## Objetivo

Este manual explica cómo dejar a Cari, Sunna, Cami y Chie funcionando desde el Bot Manager sin confundir tres cosas distintas:

1. la identidad de cada bot;
2. la comunidad donde puede trabajar;
3. la identidad humana del Maestro/Jefe.

El sistema guarda tokens y configuración en el .env local. No debe subirse al repositorio.

## 1. Crear las cuatro identidades

En Telegram, abrí @BotFather y crea cuatro bots:

- Cari
- Sunna
- Cami
- Chie

Guardá cada token en su casilla correspondiente del Bot Manager.

Al pulsar Verificar, el Manager llama a getMe para comprobar que el token es válido y obtiene automáticamente el username real del bot.

Telegram considera al token una credencial completa del bot: cualquiera que lo posea puede controlar ese bot, por lo que debe mantenerse privado.

## 2. Configurar privacidad de grupo

Por defecto, los bots nuevos utilizan Group Privacy Mode.

En @BotFather, revisá /setprivacy para cada bot.

Para este proyecto hay dos alternativas:

- convertir el bot en administrador del grupo; los bots administradores reciben todos los mensajes del grupo;
- o desactivar Group Privacy Mode y volver a agregar el bot al grupo para que la nueva configuración se aplique.

Esto es especialmente importante para las funciones de observación social. El bot no puede observar conversación ordinaria que Telegram no le entregue.

## 3. Grupo general / bienvenida

El grupo base es la comunidad principal de Ciudad Animals.

El flujo recomendado es:

1. agregar primero Chie;
2. convertirla en administradora;
3. entregarle al menos:
   - eliminar mensajes;
   - restringir integrantes;
   - gestionar temas;
4. ejecutar /configurar dentro del grupo;
5. copiar el ID numérico negativo del grupo;
6. colocarlo en Grupo general / bienvenida;
7. pulsar Fijar como hogar;
8. usar Revisar presencia en grupo.

El asistente marcará:

- ✓ cuando un requisito esté correcto;
- ⚠ cuando haya algo pendiente o no verificado;
- ✗ cuando exista un bloqueo.

Chie es la identidad de coordinación y constituye la base del onboarding y estructura del grupo.

## 4. Agregar Cari, Sunna y Cami

Cada fila del asistente tiene:

- Verificar: comprueba el token contra Telegram;
- Abrir chat: abre el privado del bot;
- Agregar al grupo: genera un enlace startgroup de Telegram y abre el selector oficial.

Cuando se pulsa Agregar al grupo, el usuario sigue realizando la incorporación en Telegram. El programa no intenta falsificar o forzar esa acción.

Después de agregar los bots, pulsá Revisar presencia en grupo.

## 5. Maestro / Jefe

El sistema utiliza un ID numérico de Telegram como identidad autoritativa del operador.

En la pantalla principal aparece:

Maestro / Jefe · ID Telegram

El botón Obtener mi ID con Chie abre un deep link de Chie. Al iniciar ese enlace, Chie devuelve el ID numérico de la persona que abrió el enlace.

También puede usarse /id directamente con cualquiera de los bots para obtener:

- ID del usuario;
- ID del chat.

El sistema no necesita guardar el número telefónico del operador. El permiso administrativo se basa en el ID numérico de Telegram.

## 6. Qué significa “hacer vivir” un bot en un grupo

“Vivir” en una comunidad significa que:

- el bot está agregado al grupo;
- Telegram le entrega los updates que necesita;
- sus permisos son suficientes para sus funciones;
- el chat figura en AUTHORIZED_CHAT_IDS;
- el grupo base, cuando corresponde, está definido como BASE_GROUP_CHAT_ID;
- su módulo está en ejecución en Bot Manager.

Por eso Agregar al grupo y Autorizar el chat son pasos diferentes.

## 7. Seguridad de acceso

Los grupos y supergrupos sólo se aceptan cuando su ID aparece explícitamente en AUTHORIZED_CHAT_IDS.

Un chat no autorizado queda fuera del runtime, incluso si un proceso automático intenta enviar una tarea.

Para un entorno de producción se recomienda usar una allowlist pequeña y explícita.

## 8. Bot Manager

La pantalla principal contiene:

- cuatro tokens y enlaces;
- Maestro/Jefe;
- grupo base;
- allowlist;
- media vault;
- canal/página de publicaciones;
- controles de IA;
- checklist de preparación;
- Asistente Telegram;
- guía BotFather/Telegram;
- Comenzar.

Una vez guardado todo, Comenzar inicia los cuatro procesos de identidad y el supervisor comprueba su arranque.

En el panel de ejecución, cada bot tiene:

- estado de proceso;
- estado de IA;
- botón iniciar/detener.

## 9. Orden operativo recomendado

Usá este orden para una instalación limpia:

1. Crear los cuatro bots con BotFather.
2. Pegar tokens.
3. Verificar los cuatro tokens.
4. Obtener el ID del Maestro/Jefe.
5. Guardarlo en Bot Manager.
6. Agregar Chie al grupo base.
7. Darle permisos administrativos requeridos.
8. Ejecutar /configurar.
9. Guardar el ID negativo del grupo como Grupo base.
10. Fijar el grupo como hogar y autorizarlo.
11. Agregar Cari, Sunna y Cami.
12. Revisar presencia y permisos.
13. Revisar /setprivacy de BotFather cuando una función necesite recibir mensajes normales.
14. Guardar configuración.
15. Pulsar Comenzar.

## 10. Qué puede y qué no puede automatizar Bot Manager

### Puede

- validar tokens mediante getMe;
- obtener usernames;
- generar enlaces privados;
- generar enlaces startgroup;
- preparar el grupo base en la configuración;
- comprobar presencia de cada bot mediante getChat + getChatMember;
- comprobar permisos administrativos conocidos;
- crear la allowlist local;
- arrancar/detener procesos;
- construir el instalador y el ZIP portable.

### No debe fingir que puede

- insertar un bot en un grupo sin que el usuario realice la acción oficial de Telegram;
- convertir mágicamente un teléfono en una identidad administrativa;
- adivinar el ID de un grupo;
- saltarse permisos de administrador;
- usar un token incorrecto o expuesto.

Telegram documenta que los enlaces start y startgroup sirven para abrir bots o preparar su incorporación a grupos, mientras que la incorporación y selección del grupo forman parte de la interacción oficial del usuario.

## 11. Diagnóstico rápido de fallos

### ✗ token rechazado

Regenerá o copiá nuevamente el token desde BotFather. Nunca lo pegues en GitHub.

### ✗ Chie no está presente

Agregá Chie al grupo base y ejecutá la revisión nuevamente.

### ⚠ faltan permisos

Promové el bot o corregí sus privilegios administrativos.

### ⚠ grupo definido pero no autorizado

El ID está colocado como grupo base, pero todavía no forma parte de AUTHORIZED_CHAT_IDS.

### ⚠ Telegram remoto: no verificado

La configuración local puede estar completa, pero todavía no se ha realizado la comprobación online del asistente.

### El bot no ve mensajes normales del grupo

Revisá Group Privacy Mode en BotFather o verificá que el bot sea administrador. Telegram limita los mensajes que recibe un bot según esa configuración.

## Referencias oficiales

- Telegram Bot Features: deep linking, start, startgroup y gestión de bots.
- Telegram Bot API: getMe, getChat, getChatMember y permisos administrativos.
- Telegram Bots FAQ: comportamiento de bots en grupos y Group Privacy Mode.
