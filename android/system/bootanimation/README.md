# Boot animation: system-build only

**Status:** design source, not installable, not shipped on stock GrapheneOS.

The stock GrapheneOS boot animation remains in place for the app-layer product.
Replacing it requires ownership of the system image, a new ADR, system-build
signing, and a boot/recovery test pass. ADR 0001 explicitly defers that work.

This directory records the source contract for that future system-image track:

- `desc.txt` declares a 1440 × 3120, 30 fps, silent animation.
- The keyframes in `assets/bootanimation/source/` are the visual source. The
  release pipeline expands them into `part0/` frames; a `bootanimation.zip` is a
  build output and must never be committed (`.gitignore` covers `*.zip`).
- No text, GrapheneOS/Android/Google/Pixel marks, flashing above 3 Hz, or audio.
- A reduced-motion variant must be produced alongside the normal animation.

Do **not** root the reference device, remount `/system`, or replace
`/system/media/bootanimation.zip` to test this. The stock-device preview in
`preview/` deliberately does not pretend to be a boot animation.

Build integration, when a future ADR authorizes it, belongs in the system image
product makefile. It must not change verified boot, AVB keys, the update trust
root, or any signing configuration.
