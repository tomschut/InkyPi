# NeoFrame support

This fork of [InkyPi](https://github.com/fatihak/InkyPi) adds a `neoframe` display type: it packs the rendered image into the Spectra-6 format the [NeoFrame](../neoframe) firmware expects, alongside a self-contained Home Assistant OS add-on. The changes are small and isolated:

- `src/display/neoframe_display.py` — new display driver (packing, decoding, preview rendering)
- `src/blueprints/frame.py` — new `/api/current_frame` route
- `src/display/display_manager.py` — registers `NeoFrameDisplay` for `display_type: "neoframe"`
- `src/inkypi.py` — registers `frame_bp`
- `src/blueprints/settings.py` / `src/templates/settings.html` — a **Panel Rotation** field on the Settings page, shown only for `display_type: "neoframe"`
- `src/utils/ingress_proxy.py` — a small WSGI middleware making `url_for()` Ingress-aware (see the "Home Assistant OS" section below); `src/inkypi.py` wires it in unconditionally (a no-op outside Ingress)
- `src/templates/inky.html` — a manual reload button, shown only when the page is actually being viewed through Ingress (no browser reload control in HA's sidebar/mobile companion app)

Everything else is unmodified upstream InkyPi. `git diff upstream/main` shows the full extent of the changes.

## Build and run

```sh
docker compose up --build -d
curl -f http://localhost:8084/api/current_frame -o current_frame.bin
```

Firmware `image_url`: `http://<inkypi-host>:8084/api/current_frame`. The original `/api/current_image` PNG route is unchanged. The frame endpoint returns 404 before a successful render and 960000 packed bytes afterwards. Identical packed output preserves mtime and ETag; changed output is atomically replaced. Conditional requests support both If-Modified-Since and If-None-Match. Failures are logged and preserve the last successful frame. Visit `http://<inkypi-host>:8084/api/current_frame?preview` in a browser to view the packed bytes decoded back into a PNG, oriented as the mounted panel will display them (not raw pixel-for-pixel bytes — no caching headers).

Configuration and images persist in Compose named volumes. On an existing installation, update its persisted device.json to display_type `neoframe` and resolution `[1600,1200]`. Upstream enhancements and inversion run before packing. Python's reference-faithful dithering can take several seconds per frame.

The panel is native 1200×1600 (GD's `EPD_WIDTH`/`EPD_HEIGHT`), matching `../neoframe`'s `nf_row_offset` layout (600-byte/1200-pixel rows × 1600 rows, split 300/300 between its two controllers) — that firmware has no rotation of its own and always expects that exact raster, so `NeoFrameDisplay` composes at a fixed 1600×1200 (InkyPi's generic `orientation`/`inverted_image` settings are unrelated to this and can be left at their defaults) and rotates by the **Panel Rotation** setting — 90° or 270°, matching however the panel is physically mounted in its enclosure — immediately before packing, so only that one setting needs to change for a different mounting or a rebuild of the enclosure. It's on InkyPi's Settings page for any `display_type: neoframe` install, backed by `device.json`'s `panel_rotation` (default 90, clockwise). This is unrelated to the stock-format comparison below, which targets a different device's convention.

## Verification

```sh
uv venv .venv
uv pip install --python .venv/bin/python pillow flask pytz python-dotenv pytest requests nodejs-wheel
.venv/bin/python -m pytest -s tests
```

To fetch the pinned reference source used only for the packing-algorithm parity test:

```sh
mkdir -p .reference
git clone https://github.com/deftdawg/neoframe.git .reference/neoframe-src
git -C .reference/neoframe-src checkout a4ccd6104d15368fc7ee15fa2ed433cc2ce44f55
```

`tests/test_neoframe.py` needs that checkout, at the commit listed in REFERENCES.md; Node 24 executes the original TypeScript directly for the parity comparison. It also imports `display.display_manager` and `blueprints.frame` directly — the real, live modules in this checkout, not a copy — to exercise packing, HTTP publication/conditional-request behavior, and settings registration in-process. Full-size comparison artifacts are written to `artifacts/`.

To verify a captured stock upload, export the exact final 1600×1200 PNG and process it in the stock tool with contrast 1, Floyd–Steinberg strength 1, sixColor, rotation 0, no scaling and no QR overlay:

```sh
.venv/bin/python scripts/compare_stock.py final.png image_data.bin
```

Source parity does not establish physical panel acceptance. A captured working-stock byte dump and firmware/panel test still require your stock output and hardware. Point the firmware at the endpoint, check its first download and panel colors/orientation, then confirm an unchanged request returns 304 and a changed render downloads a new frame.

See REFERENCES.md for format provenance and VALIDATION.md for results and environment limitations predating this fork conversion.

## Home Assistant OS

This repository is itself a Home Assistant add-on repository (`repository.yaml`), with the self-contained add-on in `inkypi_neoframe/`. In Home Assistant, add `https://github.com/tomschut/InkyPi` under **Settings → Add-ons → Add-on store → ⋮ → Repositories**, then install **InkyPi NeoFrame** from the store. See `inkypi_neoframe/DOCS.md` for full steps, including an offline fallback. `inkypi_neoframe/Dockerfile` clones this fork directly (pinned via `INKYPI_REF`, currently `v0.3.0` — bump both together when cutting a release) — it needs no syncing from the rest of this repo. Run `python3 scripts/package_addon.py` to regenerate `dist/inkypi-neoframe-haos.tar.gz` for the offline install path. Declares `amd64`, `aarch64` and `armv7`; only amd64 has actually been build-tested (see `inkypi_neoframe/DOCS.md`).
