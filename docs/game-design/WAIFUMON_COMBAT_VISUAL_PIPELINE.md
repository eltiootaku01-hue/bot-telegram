# WAIFUMON — pipeline visual de combate dual HD / Pixel Art

Fecha: 2026-09-21

## 1. Objetivo

WaifuMon utiliza dos representaciones visuales separadas para evitar cargar ilustraciones pesadas durante la batalla:

- **HD / Carta** para identidad, colección, perfil, gacha, inspección y selección de equipo.
- **Pixel Art / Chibi** para la escena de combate liviana.

La separación visual no crea una segunda fuente de verdad de gameplay.

## 2. Esquema dual por WaifuMon

### Asset A — Perfil / Colección

Ruta:

`assets/production/cards/<id>--normal.jpg`

Contrato:

- JPEG/JPG;
- 1024 × 1536;
- composición vertical;
- representación principal de la carta.

Uso:

- visor de colección;
- perfil;
- gacha;
- inspección;
- selección de equipo.

Variantes HD adicionales continúan sujetas a la matriz de arte y su compuerta correspondiente.

### Asset B — Batalla

Ruta:

`assets/production/sprites/<id>_<variant>.png`

Variantes:

| Archivo | Función |
|---|---|
| `<id>_idle.png` | Pose estática |
| `<id>_attack.png` | Ataque |
| `<id>_hit.png` | Reacción de daño |

Contrato:

- PNG;
- 128 × 128 px;
- fondo transparente;
- optimizado para canvas HTML5 2D.

Los sprites no codifican estadísticas ni reglas.

## 3. Flujo de la Mini App

### A. Selección

La pantalla de selección carga las cartas HD y permite montar un equipo de **3 WaifuMons**.

La selección transmite al backend únicamente identificadores y el estado requerido por el contrato de gameplay.

### B. Batalla

La escena de combate cambia al canvas 2D de bajo peso.

El frontend resuelve únicamente presentación:

- colocar sprites;
- reproducir idle;
- reproducir attack;
- reproducir hit;
- interpolar o temporizar movimientos visuales;
- mostrar indicadores recibidos del backend.

No decide:

- daño;
- multiplicadores elementales;
- precisión;
- HP restante;
- crítico;
- resultado de turno;
- victoria/derrota.

### C. Cut-In de habilidad especial

Cuando el backend/engine devuelve una acción `special` resuelta con éxito:

1. el frontend muestra durante **1.5 segundos** la carta HD del personaje atacante;
2. puede aplicar una transición visual ligera;
3. no recalcula el resultado;
4. retorna al canvas de sprites;
5. continúa la secuencia usando los DTOs ya resueltos.

La carta HD se usa como representación visual temporal, no como escena de combate persistente.

## 4. Autoridad del engine Java

El engine Java `WaifuMonRuleEngine.java` mantiene la autoridad exclusiva sobre el cálculo.

Para `combat.resolve`, el contrato actual produce, entre otros:

- `damage`;
- `action`;
- `critical`;
- `defender_hp`.

También valida la acción solicitada y deriva los multiplicadores desde rareza/atributos conforme a las reglas migradas.

Python y el frontend no deben duplicar esas fórmulas.

## 5. Contrato de presentación

El frontend puede transformar un resultado del engine en una intención visual:

- `attack` → sprite `attack`;
- `defend` → mantener/volver a `idle`;
- `special` → `HD cut-in 1500 ms`, después continuar con sprites;
- `defender_hp` → actualizar la barra HP;
- `critical=true` → reproducir el efecto visual de crítico.

La transformación anterior es de presentación y no modifica los valores recibidos.

## 6. Organización futura del frontend

Cuando exista la Mini App, el árbol previsto es:

```
web/
  combat/
    index.html
    combat.css
    combat.js
    assets/
      cards/       # opcionalmente cacheadas desde el backend/CDN
      sprites/     # espejo lógico de assets/production/sprites/
```

La fuente canónica de producción continúa siendo el directorio del repositorio, no una copia editada manualmente en el frontend.

## 7. Reglas de rendimiento

- El canvas de batalla debe priorizar sprites 128 × 128 sobre imágenes HD continuas.
- La carta HD solo se carga cuando la UI realmente la necesita.
- El cut-in puede precargar la carta del atacante seleccionado.
- Los sprites pueden precargarse para los tres miembros del equipo.
- Ningún asset visual debe convertirse en estado persistente de combate.

## 8. Reglas de seguridad de arquitectura

1. No duplicar la fórmula de daño en JavaScript.
2. No aceptar `defender_hp` calculado por el cliente como autoridad.
3. No usar la carta HD como sustituto del sprite en el canvas.
4. No persistir `idle/attack/hit` como reglas de gameplay.
5. No permitir que una animación determine si el ataque acertó.
6. El timeout de 1.5 s es puramente visual.
7. Un error del frontend no debe alterar el resultado ya resuelto por el engine.

## 9. Estado

La especificación queda formalizada.

La producción de sprites todavía puede estar vacía: agregar el contrato y la estructura no implica declarar que una Waifu ya tiene un sprite visual aprobado.

## 10. Frontera de seguridad de Telegram Mini Apps

La Mini App debe usar la integración oficial de Telegram para inicializarse, pero los datos entregados al cliente no se consideran autoridad de sesión por sí solos.

- El frontend puede leer `window.Telegram.WebApp.initData` para enviarlo al backend.
- `initDataUnsafe` no debe utilizarse como fuente de autenticación o autorización.
- El backend valida `initData` antes de asociar la sesión a un usuario/comunidad.
- Los identificadores de chat deben mantenerse en enteros de precisión segura; Telegram documenta que los IDs de chat pueden tener hasta 52 bits significativos.
- La URL de una Web App de producción debe ser HTTPS.

Esta frontera es independiente del engine de combate: autentica la solicitud, pero no calcula gameplay.

Referencias oficiales:

- Telegram Mini Apps: https://core.telegram.org/bots/webapps
- Telegram Bot API / WebAppInfo: https://core.telegram.org/bots/api

## 11. No duplicación de autoridad

El cliente puede solicitar una acción de combate, pero nunca puede declarar por sí mismo el daño, la precisión, los multiplicadores, el crítico o la vida restante como resultado definitivo.

El flujo es:

1. Mini App valida su contexto de Telegram en backend.
2. Backend construye un `EngineRequest` válido.
3. `WaifuMonRuleEngine.java` ejecuta `combat.resolve`.
4. Backend devuelve el DTO resuelto.
5. Mini App selecciona la animación correspondiente.

Una repetición de la solicitud usa la idempotencia del engine/backend; una repetición visual nunca crea un nuevo resultado de combate.
