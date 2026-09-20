# Catálogo de waifus / cartas

## Estado del catálogo

Fecha del snapshot: 2026-09-20.

El catálogo jugable usa dos ejes independientes:

- Popularidad: proviene de rankings externos y se guarda como ranking de referencia + puntuación normalizada para el juego.
- Poder: puntuación de balance local de 0 a 100; no pretende ser una medición objetiva del canon.

La rareza existente D/C/B/A/S/SS/SSS se deriva del poder. El tipo de carta R/SR/UR se deriva de la combinación de popularidad y poder. El elemento es independiente.

## Fuentes

Ranker: https://www.ranker.com/list/popular-anime-girls/ranker-anime
Snapshot usado: actualización del 15 de julio de 2026. Se incorporaron las posiciones 1-60 visibles en ese corte.

Anime Corner: https://animecorner.me/best-female-character-of-the-year-ranking-2025-anime-awards/
Snapshot usado: ranking anual 2025 publicado el 5 de marzo de 2026. Se incorporaron las entradas recientes no duplicadas y Anya Forger.

## Reglas de cartas

- R: promedio de popularidad y poder menor que 52.
- SR: promedio de popularidad y poder entre 52 y 77.99.
- UR: promedio de popularidad y poder igual o mayor que 78.

## Reglas de rareza

- D: poder 0-29
- C: poder 30-44
- B: poder 45-59
- A: poder 60-74
- S: poder 75-84
- SS: poder 85-94
- SSS: poder 95-100

## Alcance real

El catálogo actual no se declara como una base de todas las personajes femeninas del anime que existen. Esa colección es abierta y cambia continuamente.

Esta etapa deja terminada la arquitectura extensible y una semilla de 78 personajes jugables: 60 del snapshot Ranker, 17 adicionales del ranking anual de Anime Corner y Taiga del catálogo original.

Cada entrada puede mantener identificador, obra, ranking, popularidad, poder, rareza, carta y elemento sin cambiar el motor.

## Mantenimiento

Para cada actualización conservar fuente, fecha, ranking observado y recalcular la puntuación normalizada. El poder permanece como balance del juego.

Las imágenes no se descargan desde los rankings como dependencia de runtime. El arte entra por el flujo de medios de Cami.

## Navegación del catálogo

El panel de Sunna permite filtrar la colección sin consultar la web durante el uso del bot:

- **Elemento:** fuego, agua, tierra, aire, hielo, luz, oscuridad, rayo, mente, arcano y neutro.
- **Carta:** R, SR y UR.
- **Clase:** D, C, B, A, S, SS y SSS.
- **Fuente:** snapshot de Ranker 2026, ranking anual de Anime Corner 2025 o catálogo inicial del proyecto.

El filtro se conserva al cambiar de página. Cada personaje visible puede abrir una ficha local con su obra, carta, clase, elemento, poder de balance, popularidad normalizada, ranking de referencia y procedencia. La ficha deja explícito que el poder es una métrica de balance del juego y que la popularidad normalizada es relativa a la fuente.

Los callbacks del catálogo se mantienen compactos para respetar el límite de datos de botones inline de Telegram.
