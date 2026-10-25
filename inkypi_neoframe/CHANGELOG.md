# 0.5.0

- Playlists that are active at the same time now take turns: each refresh
  moves to the next active playlist (shortest time range first). Before,
  only the shortest one was ever shown.
- The web UI stays responsive while "Update Now" renders (4 server threads
  instead of 1).
- "Download Logs" works in the add-on: InkyPi writes a rotating log file to
  `/data/logs/inkypi.log` (kept across restarts). Chromium's error output is
  logged when a screenshot fails.
- Screenshot plugin: "Home Assistant login" toggle to capture HA dashboards
  with a long-lived access token saved as `HOME_ASSISTANT_TOKEN` on the API
  Keys page. Add `?kiosk` (kiosk-mode plugin) to hide HA's header and sidebar.

# 0.4.0

- Declared `aarch64` and `armv7` alongside `amd64` in config.yaml. Only
  amd64 has actually been build-tested; no ARM hardware or emulation was
  available to verify these before release. The main known risk is the
  Dockerfile's `apt-get install chromium` step, whose ARM packaging in
  Debian bookworm is unverified (particularly 32-bit armv7). Report back
  the add-on's build log if installation fails on ARM.

# 0.3.0

- Added a manual reload button to InkyPi's main page, shown only when
  viewed through Home Assistant's Ingress sidebar/mobile companion app
  (no browser reload control available there).

# 0.2.0

- Converted from a build-time clone-and-patch overlay of upstream InkyPi to
  a real fork with the NeoFrame changes committed directly (this repo).
- Added a Panel Rotation setting (90°/270°) on InkyPi's Settings page,
  replacing a hardcoded rotation assumption.
- Enabled Home Assistant sidebar support (Ingress), via a small
  X-Ingress-Path-aware middleware.
- The Dockerfile now pins `INKYPI_REF` to this version's git tag instead
  of tracking a moving branch, so installs are reproducible and updates
  are actually detectable.

# 0.1.0

- Initial amd64 Home Assistant OS package.
- Packed Spectra-6 endpoint alongside InkyPi PNG and web UI.
- Persistent settings, playlists, images and API keys in /data.
