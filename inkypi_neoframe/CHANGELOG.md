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
