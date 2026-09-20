# Manual de Telegram para Bot Manager

## 1. Crear los cuatro bots

En Telegram, abrir **@BotFather** y crear cuatro bots separados:

- Cari
- Sunna
- Cami
- Chie

Cada uno recibe un token diferente. El token es la credencial del Bot API y debe permanecer solamente en el `.env` local.

En BotFather también conviene comprobar que los bots puedan ser agregados a grupos y revisar Privacy Mode según el comportamiento que se necesite. Telegram documenta estas opciones en Bot Features.

## 2. Configurar el Maestro / Jefe

En **Bot Manager → Maestro / Jefe · ID Telegram** poner el ID numérico de la persona propietaria del sistema.

El campo **@usuario** es solamente una referencia visual. El permiso real utiliza el ID numérico.

El teléfono no es un identificador de autorización equivalente para este sistema: la aplicación usa el ID de usuario de Telegram que recibe la API.

## 3. Grupo base

Definir un único **Grupo general / bienvenida** mediante `BASE_GROUP_CHAT_ID`.

Ese grupo es la comunidad de referencia de Chie.

Agregar el mismo ID a `AUTHORIZED_CHAT_IDS`.

Ejemplo:

```env
BASE_GROUP_CHAT_ID=-1001234567890
AUTHORIZED_CHAT_IDS=-1001234567890
```

Un ID positivo no se acepta como grupo autorizado.

## 4. Agregar Chie primero

En **Asistente Telegram**:

1. Verificar el token de Chie.
2. Pulsar **Agregar al grupo**.
3. Telegram abrirá el selector oficial para elegir la comunidad.
4. Conceder a Chie, como mínimo, permisos de:
   - gestionar temas;
   - eliminar mensajes;
   - restringir miembros.
5. Volver a Telegram y ejecutar `/configurar` dentro del grupo con Chie.

Chie comprobará sus permisos directamente y creará los temas requeridos del Café Otaku.

El grupo debe ser un supergrupo con Foro si se pretende utilizar la estructura de temas. La gestión de temas requiere el permiso administrativo correspondiente.

## 5. Agregar Cari, Sunna y Cami

Usar el botón **Agregar al grupo** de cada identidad.

El enlace generado por el Manager es un enlace oficial de Telegram de incorporación de bots. Puede abrir el selector de grupos y, cuando corresponda, solicitar derechos administrativos sugeridos. La persona que administra Telegram sigue siendo quien confirma la incorporación.

No se intenta forzar la incorporación desde el programa.

## 6. Revisar presencia

En **Revisar presencia en grupo**, el Manager consulta:

- si el token funciona;
- identidad y `@username`;
- existencia del grupo;
- presencia del bot;
- estado del bot;
- permisos requeridos;
- configuración de Chie;
- grupo autorizado.

Interpretación:

- **✓** correcto;
- **⚠** presente pero requiere atención;
- **✗** falta algo que impide considerar completa la instalación.

## 7. Orden recomendado de puesta en marcha

```text
Maestro/Jefe
    ↓
tokens de Cari/Sunna/Cami/Chie
    ↓
grupo general identificado
    ↓
grupo agregado a AUTHORIZED_CHAT_IDS
    ↓
Chie agregada como administradora
    ↓
/configurar
    ↓
temas del Café Otaku
    ↓
Cari + Sunna + Cami agregadas
    ↓
Revisar presencia
    ↓
Guardar configuración
    ↓
Comenzar
```

## 8. Función de cada avatar

**Chie** es la base operativa de la comunidad: recepción, configuración, permisos, avisos y coordinación.

**Cari** mantiene presencia comunitaria y herramientas explícitas de moderación.

**Sunna** gestiona WaifuMon, colección, encuentros, combate y trivia.

**Cami** gestiona archivo, medios, pedidos, publicaciones y estadísticas.

**Tío Otaku** continúa siendo una identidad humana operada manualmente; el sistema no lo convierte en un quinto bot autónomo.

## 9. IA

La IA es opcional.

Con `AI_ENABLED=false` los comandos, economía, juegos, comunidad y runtime determinista continúan funcionando sin LLM.

La ruta local recomendada para una máquina con poca RAM es Ollama, siempre que el modelo elegido entre en los recursos disponibles.

## 10. Seguridad

No subir nunca:

- tokens de Telegram;
- claves Gemini/Groq/Cerebras/OpenRouter;
- archivos `.env`;
- credenciales privadas.

El repositorio solamente debe contener `.env.example`.

## 11. Qué puede hacer y qué no puede hacer el Manager

Puede:

- validar tokens mediante `getMe`;
- identificar el bot y recuperar su `@username`;
- generar enlaces oficiales para agregar bots a grupos;
- revisar pertenencia y permisos cuando existe un ID de grupo;
- guardar el grupo base;
- mantener una lista explícita de comunidades autorizadas;
- mostrar visualmente qué parte de la instalación falta.

No puede:

- introducir silenciosamente un bot en un grupo donde el usuario no autoriza la incorporación;
- convertir una cuenta de Telegram en bot;
- obtener el número telefónico privado del Maestro como sustituto del ID;
- conceder permisos administrativos sin la autoridad del usuario/administrador de Telegram.

Telegram documenta los enlaces `startgroup` para incorporar bots y los derechos administrativos sugeridos, además de las opciones de privacidad y gestión de grupos.
