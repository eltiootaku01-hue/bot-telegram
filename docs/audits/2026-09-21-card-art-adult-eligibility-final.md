# REPORTE ATÓMICO FINAL — WaifuMon Card Art Matrix v2 / Elegibilidad Adulta

Fecha: 2026-09-21

## 1. Windows Build #1872

- Workflow: `Windows build`
- Run: `#1872`
- SHA auditado: `aaf8df4a6277d381da52aafb061b6a34a2e9b867`
- Resultado: `SUCCESS`
- Artefactos:
  - `bot-telegram-windows-installer`
  - `bot-telegram-windows-portable`
- Instalador: 139,383,737 bytes
- Portable: 140,500,753 bytes
- Ambos artefactos quedaron publicados y no expirados en la ejecución auditada.

## 2. Elegibilidad adulta

El catálogo contiene 78 cartas y 19 UR con soporte `ur-alt-holo`.

Se habilitaron exactamente 6 cartas con condición adulta inequívoca documentada:

- `erza-scarlet` — Erza Scarlet — 19 años
- `esdeath` — Esdeath — 20 años
- `nami` — Nami — 20 años después del salto temporal
- `nico-robin` — Nico Robin — 30 años después del salto temporal
- `tsunade` — Tsunade — 50–51 años en Parte I
- `yor-forger` — Yor Forger — 27 años

Los otros 13 UR ALT permanecen `adult_eligible=false`. Esto incluye casos escolares, menores en su representación relevante o con edad adulta no suficientemente establecida para superar esta compuerta conservadora.

La elegibilidad no se deriva de la rareza UR. `UR_ALT_HOLO` sigue siendo una variante adulta, no explícita y doblemente revisada.

## 3. Consistencia de manifiestos

Los tres registros están sincronizados para las mismas seis cartas:

- `assets/waifus/art_manifest.json`
- `assets/waifus/card_art_qa_manifest.json`
- `assets/waifus/card_art_prompt_manifest.json`

El validador fue endurecido para rechazar divergencias entre el manifiesto de arte y el QA sobre `adult_eligible`.

## 4. Primeros tres prompts UR ALT Holo

Los primeros tres registros elegibles en el orden del catálogo son:

1. Erza Scarlet
2. Esdeath
3. Nami

Los prompts completos están en:

`docs/generated/WAIFUMON_UR_ALT_HOLO_FIRST3_PROMPTS.md`

Todos usan el modo premium no explícito: sin desnudez, sin exposición íntima, sin actividad sexual y con oclusión contextual opcional.

## 5. QA

Card Art Production `#46` y la revalidación `#47` terminaron en `SUCCESS`.

La etapa exacta:

`python tools/validate_card_qa.py`

produjo:

`Card visual QA contract validated: 78 cards tracked, 1 canonical cards approved, 1 variants approved.`

También terminaron correctamente la validación técnica de assets y los tests específicos de arte. La ejecución `#47` corrió sobre el SHA que ya contiene las seis elegibilidades.

## 6. Evidencia externa de edad

- Erza Scarlet: 19 años. https://fairytail.fandom.com/wiki/Erza_Scarlet
- Esdeath: 20 años. https://akamegakill.fandom.com/es/wiki/Esdeath
- Nami: 20 años después del salto temporal. https://onepiece.fandom.com/wiki/Nami
- Nico Robin: 30 años después del salto temporal. https://onepiece.fandom.com/wiki/Nico_Robin
- Tsunade: 50–51 años en Parte I. https://naruto.fandom.com/es/wiki/Tsunade
- Yor Forger: 27 años. https://us.oricon-group.com/news/5593/

## 7. Regla de publicación

`adult_eligible=true` no aprueba por sí solo una variante.

La producción continúa requiriendo:
- prompt no explícito;
- anatomía y encuadre válidos;
- revisión primaria;
- segunda revisión independiente para UR;
- asset técnico JPG/JPEG 1024x1536;
- contrato QA satisfecho.

La infraestructura permanece fail-closed ante sexualización de menores o contenido explícito.
