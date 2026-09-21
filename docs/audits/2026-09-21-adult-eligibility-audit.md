# Auditoría de elegibilidad adulta — WaifuMon UR ALT Holo

Fecha: 2026-09-21
Base auditada: `aaf8df4a6277d381da52aafb061b6a34a2e9b867`

## Resultado del Windows Build #1872

El workflow `Windows build` #1872 asociado al SHA `aaf8df4a6277d381da52aafb061b6a34a2e9b867` terminó en `success`.

Las etapas críticas también terminaron correctamente: pruebas nativas de media/encoder, validación de assets de cartas, exportador de prompts, compilación de los cinco ejecutables, verificación visual/producción, verificación del runtime Java de WaifuMon, smoke test de BotManager, instalador, ZIP portable y checksums.

Artefactos publicados por la ejecución:

- `bot-telegram-windows-installer`
- `bot-telegram-windows-portable`

## Política de elegibilidad

`adult_eligible` se usa como compuerta explícita para `UR_ALT_HOLO`.

Para este ciclo se habilitaron únicamente seis cartas con edad adulta inequívoca en las fuentes revisadas:

| character_id | personaje | base de elegibilidad |
| --- | --- | --- |
| erza-scarlet | Erza Scarlet | 19 años |
| esdeath | Esdeath | 20 años |
| nami | Nami | 20 años después del salto temporal |
| nico-robin | Nico Robin | 30 años después del salto temporal |
| tsunade | Tsunade | 50–51 años en Parte I |
| yor-forger | Yor Forger | 27 años |

No se habilitaron los restantes UR ALT Holo porque son escolares/menores en su representación relevante o porque su edad adulta no quedó establecida con el mismo nivel de evidencia. Entre los casos conservados en `false` están Akame, Akeno Himejima, Asuna, Momo Ayase, Ochako Uraraka, Rias Gremory, Oguri Cap, Power, Makima, Kuroka, Yoruichi, Albedo y Sakiko Togawa.

La compuerta sigue siendo independiente de rareza: ser UR no convierte por sí mismo a una carta en adulta.

## Sincronización de manifiestos

Se actualizaron de forma consistente:

- `assets/waifus/art_manifest.json`
- `assets/waifus/card_art_qa_manifest.json`
- `assets/waifus/card_art_prompt_manifest.json`

Además, `tools/validate_card_qa.py` ahora verifica que la elegibilidad adulta del QA y del manifiesto de arte no puedan divergir.

## Primeros tres prompts inspeccionables

Después del filtrado adulto conservador, los primeros tres registros con `UR_ALT_HOLO` habilitado son:

1. Erza Scarlet
2. Esdeath
3. Nami

Los prompts completos y formateados están en:

`docs/generated/WAIFUMON_UR_ALT_HOLO_FIRST3_PROMPTS.md`

Todos permanecen explícitamente no gráficos/no explícitos: sin desnudez, sin exposición íntima, sin actividad sexual y con oclusión visual solo como recurso de composición.

## QA

`tools/validate_card_qa.py` debe continuar siendo la fuente de verdad antes de aprobar cualquier variante. Una variante UR ALT no puede considerarse aprobada solo porque `adult_eligible=true`; mantiene requisitos de anatomía, manos, perspectiva, encuadre, no explicitud, revisión primaria y segunda revisión independiente.

## Referencias externas revisadas

- Erza Scarlet: 19 años en Fairy Tail. https://fairytail.fandom.com/wiki/Erza_Scarlet
- Esdeath: 20 años en Akame ga Kill!. https://akamegakill.fandom.com/es/wiki/Esdeath
- Nami: 20 años después del salto temporal. https://onepiece.fandom.com/wiki/Nami
- Nico Robin: 30 años después del salto temporal. https://onepiece.fandom.com/wiki/Nico_Robin
- Tsunade: 50–51 años en Parte I. https://naruto.fandom.com/es/wiki/Tsunade
- Yor Forger: 27 años. https://us.oricon-group.com/news/5593/
- Momo Ayase: 16–17 años y estudiante de secundaria. https://dandadan.fandom.com/wiki/Momo_Ayase
- Ochako Uraraka: 15–16 durante la etapa escolar y 24 en el presente de la historia. https://myheroacademia.fandom.com/wiki/Ochaco_Uraraka
- Akeno Himejima: 18 en los volúmenes 1–22 y 19 posteriormente, pero vinculada a Kuoh Academy; se conserva false por la regla de prudencia aplicada al catálogo. https://highschooldxd.fandom.com/wiki/Akeno_Himejima
