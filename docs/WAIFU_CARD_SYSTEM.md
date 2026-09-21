# Sistema de cartas de WaifuMon

## Contrato de rareza de carta

Las cartas tienen una escala independiente del poder de combate:

- R: personaje genérico original de Ciudad Animals.
- S: personaje conocido del catálogo.
- SR: personaje muy popular según las fuentes de popularidad registradas.
- UR: carta de fusión creada a partir de dos personajes base diferentes.

La clase D/C/B/A/S/SS/SSS sigue siendo una escala de balance de combate y no convierte por sí sola una carta base en UR.

## Variantes visuales

Cada carta base puede resolverse de manera determinista a partir de una semilla:

- normal: vestuario cotidiano, aventura, deporte, café, formal u otras variaciones de estilo general.
- shiny: vestuario especial, por ejemplo uniforme de trabajo, temática animal, cosplay, festival, idol, detective, battle dress o temporadas.

La variante no altera las reglas económicas, el poder ni la identidad de la carta.

## Fusión UR

Una UR se genera solamente desde dos cartas base diferentes que el mismo perfil posee.

La operación valida propiedad y copias, comprueba que ambas cartas no sean una UR, decrementa exactamente una copia de cada carta, crea la nueva carta UR y persiste la fusión en una única transacción.

Si cualquiera de las dos cartas deja de estar disponible durante la operación, la transacción se revierte.

## Arte

El runtime espera imágenes finales en formato JPEG de 1024 x 1536 px y hasta 8 MiB.

El nombre canónico es assets/waifus/<character_id>--normal.jpg o assets/waifus/<character_id>--shiny.jpg.

## Generación con reintentos

tools/render_card_asset.py ejecuta un proveedor externo o local mediante una plantilla de comando. {prompt_file} recibe la dirección visual y {output} es el JPEG final.

El renderer permite como máximo 100 intentos por asset, registra cada intento, valida el código de salida, valida formato, valida dimensiones, valida tamaño y solo acepta un asset cuando todas las comprobaciones pasan.

El proveedor concreto permanece desacoplado del juego.

## Seguridad visual

La aplicación no convierte el sistema de cartas en una instrucción para representar contenido sexual explícito. La dirección especial se limita a diseños de vestuario y presentación no explícitos. Los personajes que no están explícitamente aprobados para una dirección adulta permanecen siempre en la dirección estándar apropiada.

## GitHub y Telegram

GitHub bloquea objetos mayores de 100 MiB y recomienda mantener los objetos individuales pequeños para preservar rendimiento. Telegram permite fotos subidas por multipart/form-data de hasta 10 MB. El proyecto fija 8 MiB como techo interno para los JPEG de cartas.

Fuentes verificadas el 21 de septiembre de 2026: GitHub Docs sobre límites de repositorio y archivos grandes; Telegram Bot API y Bots FAQ.

La referencia visual externa no es autoridad sobre el canon del juego. Solo sirve como entrada de producción de assets.