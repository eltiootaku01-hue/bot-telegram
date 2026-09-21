# Cartilla de stickers — Cari, Sunna, Cami y Chie

Fecha: 2026-09-21.

La cartilla define el lenguaje visual mínimo para que las cuatro identidades puedan expresarse con stickers sin convertir los stickers en una segunda fuente de personalidad.

## Reglas visuales
- Formato maestro: cuadrado 512×512.
- Fondo: transparente.
- Contorno: limpio y legible a tamaño pequeño.
- Expresión: una emoción clara por sticker.
- Texto: corto; el texto no reemplaza el significado de la pose.
- Los personajes conservan su peinado, colores, rasgos y accesorios base entre stickers.
- No se usan poses sexualizadas, desnudez ni contenido gráfico.
- Las variantes premium de juego no cambian la identidad del personaje.

## Cartilla por personaje

### Cari — energética y protectora

| Intent | Pose | Expresión | Atrezzo | Texto |
|---|---|---|---|---|
| greeting | saludo con una mano | sonrisa abierta | tacita | ¡Hola! |
| called | se gira rápido | sorpresa alegre | campanita | ¿Sí? |
| affection | se inclina con cariño | sonrisa cálida | juguito | Awww… |
| reassurance | pulgar arriba | calma segura | delantal | Todo bien. |
| belonging | abre los brazos | protectora | mesa | Hay lugar. |
| farewell | agita la mano | tranquila | tacita | ¡Nos vemos! |
| thanks | junta las manos | alegre | juguito | ¡Gracias! |
| celebration | pequeño salto | ojos brillantes | confeti | ¡Yay! |
| confusion | inclina la cabeza | confusión simpática | libretito | ¿Eh? |
| busy | corre con prisa | concentración divertida | dos tazas | ¡Ya voy! |
| game_success | puño arriba | orgullo alegre | ficha | ¡Victoria! |
| game_miss | se tapa la cara | sorpresa teatral | dado | ¡Oh no! |

### Sunna — reservada y sensible

| Intent | Pose | Expresión | Atrezzo | Texto |
|---|---|---|---|---|
| greeting | saludo pequeño | sonrisa tímida | control | Hola. |
| called | mira de reojo | atención contenida | audífonos | Hm? |
| affection | se acerca un poco | sonrisa suave | bufanda | Gracias… |
| reassurance | asiente despacio | calma serena | control | Estoy bien. |
| belonging | se sienta con el grupo | sonrisa discreta | cojín | Hay lugar. |
| farewell | levanta dos dedos | despedida tranquila | control | Nos vemos. |
| thanks | inclina la cabeza | gratitud sincera | regalo | Gracias. |
| celebration | puño arriba | alegría contenida | trofeo | Bien. |
| confusion | mira la pantalla | duda curiosa | manual | No entiendo. |
| busy | juega concentrada | concentración | controles | Espera. |
| game_success | muestra ficha | satisfacción | trofeo | Ganamos. |
| game_miss | parpadea sorprendida | decepción leve | dado | Hm… |

### Cami — analítica y observadora

| Intent | Pose | Expresión | Atrezzo | Texto |
|---|---|---|---|---|
| greeting | saluda con una carpeta | sonrisa discreta | ficha | Hola. |
| called | levanta la vista | atención serena | lápiz | ¿Sí? |
| affection | ofrece una nota | ternura contenida | papelito | Lo valoro. |
| reassurance | señal de calma | serenidad | checklist | Está bien. |
| belonging | señala una silla | amabilidad discreta | silla | Puedes quedarte. |
| farewell | cierra una carpeta | despedida tranquila | archivo | Hasta luego. |
| thanks | anota algo | gratitud tranquila | lápiz | Gracias. |
| celebration | muestra una ficha | satisfacción discreta | sello | Completado. |
| confusion | compara fichas | duda analítica | documentos | No coincide. |
| busy | revisa documentos | concentración | carpetas | Un momento. |
| game_success | muestra ficha ganadora | orgullo sereno | marcador | Buen resultado. |
| game_miss | marca una corrección | sorpresa leve | lápiz | Reviso. |

### Chie — coordinadora nerviosa

| Intent | Pose | Expresión | Atrezzo | Texto |
|---|---|---|---|---|
| greeting | saludo nervioso | sonrisa tímida | carpeta | B-buenas… |
| called | se sobresalta | sorpresa nerviosa | campanita | ¿S-sí? |
| affection | junta las manos | felicidad tímida | corazón de papel | G-gracias… |
| reassurance | respira y asiente | calma tímida | lista revisada | Todo en orden. |
| belonging | ofrece una silla | sonrisa nerviosa | recepción | H-hay lugar. |
| farewell | se despide con ambas manos | sonrisa tímida | agenda | H-hasta pronto. |
| thanks | pequeña reverencia | gratitud nerviosa | nota | G-gracias. |
| celebration | levanta lista aprobada | alegría nerviosa | confeti mínimo | ¡S-salió bien! |
| confusion | mira una lista al revés | confusión nerviosa | papeles | ¿E-eh? |
| busy | ordena listas | concentración nerviosa | tres carpetas | U-un momento… |
| game_success | levanta sello | sorpresa feliz | sello aprobado | ¡S-sí! |
| game_miss | manos en la cabeza | susto cómico | papel arrugado | ¡A-ay! |

## Flujo de generación
1. app/stickers/catalog.py define el contrato.
2. sticker_prompt() produce un prompt visual seguro.
3. El artista o generador crea el PNG maestro con fondo transparente.
4. Se convierte a WebP/Sticker según el paquete actual de Telegram.
5. El file_id de Telegram se registra fuera del prompt, asociado al sticker_key.
6. El runtime selecciona el sticker por BotIdentity + CharacterIntent; nunca inventa claves.

## Fuente de verdad
La personalidad continúa en app/characters/. Los stickers solo representan una expresión preautorizada. La selección es determinista para poder probarla y reproducirla.