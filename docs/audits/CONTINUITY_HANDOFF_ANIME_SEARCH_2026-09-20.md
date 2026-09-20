# Handoff — búsqueda local de anime por personaje

Fecha: 2026-09-20

- AnimeCatalogService.search_works() ahora busca también en AnimeCharacter.name y AnimeCharacter.aliases_json.
- La consulta usa outer join + distinct para mantener una obra una sola vez cuando coinciden varios personajes/aliases.
- La búsqueda sigue siendo 100% local; no se agregó red ni LLM.
- Se añadió regresión en tests/test_anime_catalog.py para encontrar una obra por nombre de personaje y por alias.
- Commit de código/test: 2b6ba15a9f7aa1e89db28948531a6d2546e7112e.
- No repetir esta mejora como pendiente.
- Validación pendiente: CI y Windows sobre el SHA final.
- Producto global provisional: 82%; esta mejora eleva la superficie funcional de Cami pero no justifica aún cambiar el porcentaje global.
