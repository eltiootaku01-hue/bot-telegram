# Ciudad Animals — Arco 01: El Café se vuelve hogar

Estado: **ficción de runtime propuesta; no es canon de la obra principal**.

Este arco convierte el Café Otaku en una pequeña línea narrativa recorrible por la comunidad. No usa IA generativa, no altera las biblias de personajes y no puede convertir hechos no confirmados de la historia principal en canon.

## Capítulos

### 1. Las luces del Café
Chie ordena la recepción, Cari prepara el salón, Cami organiza el archivo y Sunna observa desde la zona de juegos. Cari deja una silla libre sin exigir que Sunna participe.

**Juego relacionado:** el Café establece sus cuatro espacios funcionales.

### 2. Una partida a medias
Sunna deja una partida para mirar el movimiento del salón y, por primera vez, decide quedarse en lugar de desaparecer.

**Juego relacionado:** WaifuMon y los juegos funcionan como puerta de entrada a pertenencia, no solo como competición.

### 3. El caso de la cuchara
Cami plantea un misterio cotidiano que las cuatro pueden resolver sin convertir el incidente en un hecho importante de la obra.

**Juego relacionado:** misterio basado en pistas explícitas y respuesta verificable.

### 4. No tenés que hacerlo sola
Cari y Sunna reflejan dos respuestas opuestas al miedo: cargar con todo o desaparecer para no molestar. La escena no exige una resolución épica; permanecer juntas ya es el avance.

**Juego relacionado:** las actividades del Café pueden crear escenas compartidas sin premiar únicamente al ganador.

### 5. La recepción no está sola
Chie intenta resolver demasiadas tareas y descubre que coordinar también significa pedir ayuda y repartir responsabilidades.

**Juego relacionado:** onboarding, permisos, pedidos y coordinación deben reducir carga administrativa, no añadirla.

### 6. El Café se vuelve hogar
Cada personaje mantiene su función y su identidad. Tío Otaku puede aparecer cuando el operador humano decida hacerlo; el sistema nunca escribe por él.

**Juego relacionado:** todas las mecánicas deben reforzar pertenencia y continuidad sin convertirse en obligación.

## Reglas narrativas

- Las escenas anteriores son independientes del canon principal.
- No se inventan diseños, cronologías, poderes, infancia ni acontecimientos futuros de Cari, Cami, Sunna o Chie.
- Sunna conserva su identidad como persona y no se reduce a una respuesta monosilábica.
- Cari no se convierte en una heroína que siempre resuelve todo sola.
- Cami no se reduce a una máquina de datos.
- Chie coordina y comprueba, pero no se inventa una autoridad narrativa que todavía no tiene.
- Tío Otaku sigue siendo un personaje humano operado manualmente.
- El arco no otorga puntos ni ventajas competitivas: su función es narrativa.

## Arquitectura

La posición se guarda por comunidad en la tabla `story_progress` usando el arco `cafe-origenes-v1`.

Los botones contienen el número de capítulo esperado. Si alguien pulsa un botón antiguo después de que otra persona haya avanzado, el servidor no salta capítulos: devuelve el estado actual.

Esta defensa evita que la historia se rompa por mensajes antiguos, doble clics o varios participantes avanzando al mismo tiempo.

## Por qué este diseño

La investigación pública usada para el diseño de juegos muestra una tensión repetida entre azar/grindeo y sensación de progreso. En gacha se repiten quejas sobre largas rachas sin resultados útiles y duplicados, mientras que en juegos de deducción se valora que exista una solución demostrable y que las pistas permitan llegar a ella sin adivinar.

Por eso este arco no usa la historia como otra obligación diaria ni como moneda. Las mecánicas de cada personaje tienen que aportar una decisión o una escena, no solo otro contador.
