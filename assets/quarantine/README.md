# Asset quarantine

These files are intentionally excluded from production.

Reasons currently represented:

- legacy SVG artwork: outside the production JPEG contract;
- generated concepts/drafts: not approved final card art;
- existing raster assets: not validated against the current 1024×1536 production contract from repository bytes in this environment.

Nothing under this directory may be loaded by the production WaifuMon runtime.

Promotion path:

1. validate with the repository asset validator;
2. verify exactly 1024×1536 JPEG output;
3. update the asset manifest;
4. move the approved file into `assets/production/cards/`;
5. rerun Python, Java and packaging tests.
