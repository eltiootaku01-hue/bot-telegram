# WaifuMon production card assets

This directory is the only production location for collectible card art.

## Hard contract

Every production card asset MUST be:

- JPEG/JPG file only;
- exactly **1024 × 1536** pixels;
- readable as a valid JPEG;
- between 50 KiB and 8 MiB;
- named `<character-id>--<variant>.jpg` for normal/shiny card variants, or `<character-id>--stage<1|2|3>.jpg` for level-derived evolution art;
- approved before entering this directory.

Every production file must also have an asset-level entry in `assets/waifus/provenance_manifest.json`. New assets must use `licensed` (explicit modification + redistribution rights) or `original`; `grandfathered_legacy` exists only for pre-existing files whose original provenance cannot currently be reconstructed.

The runtime must fail closed when an asset is absent or fails validation. Drafts, concepts, vectors and legacy assets stay under `assets/quarantine/`.

No PNG, WebP or other raster format is accepted here.

External assets that permit use but prohibit redistribution MUST NOT be copied into
this directory. Removing a watermark, cropping around a signature, recoloring, or otherwise transforming an image does not create redistribution rights. Temporary/uncleared source files belong in `assets/quarantine/`.
See `docs/assets/INTERNATIONAL_ASSET_RADAR.md` for the provenance gate.
