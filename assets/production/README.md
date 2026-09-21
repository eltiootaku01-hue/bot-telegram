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

The runtime must fail closed when an asset is absent or fails validation. Drafts, concepts, vectors and legacy assets stay under `assets/quarantine/`.

No PNG, WebP or other raster format is accepted here.
