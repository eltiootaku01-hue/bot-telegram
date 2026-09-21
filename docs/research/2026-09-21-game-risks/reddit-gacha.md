# Reddit — fallos de diseño observados

## Pity y mala suerte

Las discusiones públicas consultadas repiten tres molestias: ausencia o poca claridad del pity, muchas tiradas sin el objetivo buscado y sensación de que los duplicados no compensan el esfuerzo.

Decisión para WaifuMon:
- pity suave de D persistente;
- coste visible antes de tirar;
- registro durable de cada tirada;
- compensación futura de duplicados mediante colección/evolución, evitando perder completamente el valor de una copia.

## Cooldown y reclamación

En Mudae aparecen reglas comunitarias para reducir discusiones por reclamaciones y se observa que el cooldown de claim es una parte muy visible del juego.

Decisión para WaifuMon:
- las reclamaciones se resuelven en SQL;
- un usuario solo tiene una oportunidad por encuentro;
- un encuentro público tiene un máximo de tres participantes;
- el resultado no depende de quién consiga pulsar repetidamente un botón.

## Duplicados

Las conversaciones sobre gacha muestran que el duplicado puede sentirse como castigo cuando no tiene una utilidad clara.

Decisión para WaifuMon:
- una copia extra siempre aumenta colección y experiencia;
- la evolución consume copias con reglas explícitas;
- la interfaz muestra copias restantes;
- no se crea un sistema de duplicados que desaparezca silenciosamente.

Fuentes públicas:
- https://www.reddit.com/r/gachagaming/
- https://www.reddit.com/r/heartopia/
- https://www.reddit.com/r/Mudae/
