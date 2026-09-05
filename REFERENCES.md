# Reference provenance

InkyPi: https://github.com/fatihak/InkyPi/tree/2ff58067d05356802d95884c0bb7d8d03d205087

Packing and dithering: https://github.com/deftdawg/neoframe/blob/a4ccd6104d15368fc7ee15fa2ed433cc2ce44f55/src/algorithms.ts

The Python port follows rgbToLab, findClosestColor, floydSteinbergDither and the sixColor branch of processImageData. Palette order is yellow, green (41,204,20), blue, red, black, white; panel codes are 2,6,5,3,0,1. `encode_frame()` itself packs whatever image it is given: pixels traverse rows left-to-right, top-to-bottom, first pixel in the high nibble. This section describes the algorithm as validated against the stock tool on a 1600×1200 landscape input (960000 bytes, no header); `NeoFrameDisplay.display_image()` instead rotates the composed 1600×1200 image by the `panel_rotation` setting (90° default) before calling `encode_frame()`, to match `../neoframe`'s native 1200×1600 panel raster — see README.md.

The final InkyPi image is the comparison input. Set stock contrast to 1, strength to 1, sixColor, floydSteinberg, rotation 0, and disable QR overlays. Stock's default contrast 1.2 is an upstream image enhancement and must not be applied again to the final image.

Reference-source parity is distinct from a captured physical stock upload and panel validation. Neither physical acceptance milestone can be claimed without those artifacts/hardware.
