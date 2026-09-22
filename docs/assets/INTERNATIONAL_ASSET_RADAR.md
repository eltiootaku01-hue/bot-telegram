# International asset radar

Checked: 2026-09-21

This document is a provenance gate, not a download list. The project may study old
communities for techniques and references, but production bytes only enter the
repository when redistribution/modification rights are explicit.

## Japan / doujin and freeware ecosystem

### BOOTH — free cyberpunk overlay materials

Source:
https://booth.pm/ja/items/5102452

Observed terms:
- personal and commercial use permitted;
- color adjustment and light modification permitted;
- redistribution and resale prohibited.

Decision: REFERENCE ONLY / DO NOT BUNDLE.

The material is useful as a visual reference for the BŌSŌZOKU direction, but the
terms prohibit redistributing the source asset.

### BOOTH — pixel-art effects

Source:
https://booth.pm/ja/items/8229258

Observed terms:
- modification permitted;
- commercial use permitted;
- redistribution prohibited.

Decision: REFERENCE ONLY / DO NOT BUNDLE.

### Japanese Canvas / danmaku research

`you-sk/vector-sht-manus` is a Japanese-language project using HTML5 Canvas and
vanilla JavaScript and is released under MIT. Its code structure is suitable as a
reference for lightweight Canvas game architecture; the project is not copied
verbatim into this repository.

Decision: CODE REFERENCE — MIT.

The repository license grants reuse, modification and distribution subject to
retaining the copyright/license notice.

## Germany / RPG Maker and 2D game communities

### Valentine90 / abs-rpg-maker

The repository is marked MIT and is useful as a reference for a lean real-time
battle architecture.

Important boundary: the repository contains RPG Maker project data and graphics in
addition to code. The MIT label for the repository must not be interpreted as a
blanket relicensing of every embedded RPG Maker resource.

Decision: CODE REFERENCE; ASSET BYTES NOT IMPORTED.

### RPG Maker official licensing

RPG Maker's own documentation distinguishes assets that are usable inside RPG
Maker projects from assets that can be reused outside the engine. XP's built-in
graphics are not automatically cleared for standalone redistribution.

Decision: DO NOT IMPORT RPG Maker RTP/engine assets without the applicable license.

## Hispanic MUGEN / Flash ecosystem

MUGEN communities are valuable for studying hit-spark vocabulary and low-weight
sprite workflows, but a resource-board listing is not proof of redistribution
rights.

Mugen Free For All provides a large resource center for character, system, stage
and effect sprites. The Spriters Resource also documents restrictions around
custom MUGEN sprite rips.

Decision: QUARANTINE / NO AUTOMATIC RIPPING.

## India / Russia / J2ME / Symbian

### SourceForge J2ME Games

The SourceForge project `J2ME Games` is MIT-licensed and focuses on small Java ME
games and simple interfaces.

Decision: CODE REFERENCE — MIT. Do not assume that a game's external assets,
screens or extracted files are separately redistributable.

### j2meDash

The `j2meDash` repository is GPL-3.0. It is useful for studying very small
Java ME game constraints, but its license does not make unrelated historical
game assets freely redistributable.

Decision: REFERENCE ONLY unless a component is intentionally incorporated under
compatible GPL terms.


## Additional historical references

### freem.jp / ふりーむ！

FreeM pages can expose the exact plugins, pixel-art packs and effect sources used
by individual freeware authors. That makes them useful provenance leads, but the
mere presence of a credit or a downloadable game does not by itself grant the
repository redistribution rights. For example, one page credits several
third-party pixel/effect sources without publishing a blanket license for those
source files.

Decision: **REFERENCE / MANUAL LICENSE REVIEW ONLY**.

### RPG-Atelier / Velsarbor

The official Velsarbor site states that its game resources are freely available
with attribution, while asking users not to copy the main characters exactly.
This is a useful lead for studying older RPG Maker resource workflows, but any
candidate file should still be recorded at asset level before promotion.

Decision: **CANDIDATE / PROVENANCE REQUIRED**.

### SourceForge JGame

JGame is a small 2D engine that explicitly supports Java ME and is distributed
under a BSD license. It is a good reference for tiny state/render loops suitable
for memory-constrained interfaces.

Decision: **CODE REFERENCE — BSD**.

### SourceForge Fire-j2me

Fire-j2me is a lightweight, themable MIDP2 GUI library released under the LGPL.
Its historical UI architecture is relevant to low-weight mobile menus and
skin systems.

Decision: **CODE REFERENCE — LGPL**.


## Lightweight Canvas implementation chosen for this project

Rather than importing a historical minified library, this repository now contains
an original Canvas effects module at `webapp/js/effects.js`.

It uses:
- a fixed maximum particle count;
- short-lived particles with circles/streaks;
- additive compositing;
- bounded frame-step time;
- no external JavaScript dependency;
- the existing BŌSŌZOKU red/violet/yellow visual language.

This makes the effect layer small enough for a Telegram Mini App while avoiding
third-party asset redistribution.

## Magenta cleanup tool

Use:

```text
python -m pip install "Pillow>=11,<13"
python tools/prepare_magenta_png.py INPUT.png assets/production/sprites/OUTPUT.png
```

Only run this after the source asset has passed the provenance gate above. The tool
performs one mechanical transformation: `#FF00FF → alpha=0`. It does not grant
any license or make an otherwise restricted asset redistributable.

## Production policy

- No unlicensed game rips.
- No assumed rights from “free download” status.
- No copying of dead-forum assets merely because the page is old.
- No promotion from quarantine without a license/provenance record.
- Original/recreated Canvas effects are preferred when the source mechanic can be
  implemented cleanly without importing third-party bytes.
