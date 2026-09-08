# Install on Home Assistant OS

This add-on declares **amd64**, **aarch64** and **armv7** (32-bit) HAOS. Supervisor builds InkyPi locally on your HAOS machine, natively for whichever architecture it's running on, so the first installation needs internet access and can take several minutes — longer on ARM hardware.

Only amd64 has actually been build-tested (see Scope and verification below). The Dockerfile installs `chromium` via apt, which is the main real risk on ARM — Debian's chromium packaging for 32-bit armhf/armv7 has been inconsistent across releases, so a first install on `armv7` in particular may fail at that step. If it does, please share the add-on's build log so the Dockerfile can be adjusted for that architecture specifically.

## Add the repository

1. In Home Assistant, open **Settings → Add-ons → Add-on store** (called **Settings → Apps → App store** on newer versions).
2. Open the **⋮** menu (top right) → **Repositories**.
3. Add `https://github.com/tomschut/InkyPi` and click **Add**, then close the dialog. The store reloads; if the new add-on doesn't appear, reload the page.
4. Find **InkyPi NeoFrame** in the store, choose **Install**, then **Start**. Enable **Start on boot** and, optionally, **Watchdog**.
5. Select **Open Web UI** (or find **InkyPi NeoFrame** in the sidebar — Ingress is enabled, so it's added automatically; toggle **Show in sidebar** on the add-on's Info page to hide it), or visit `http://<HAOS-IP>:8084/`. Create your image content and playlists in InkyPi.
6. Set the Project 1 firmware's `image_url` to `http://<HAOS-IP>:8084/api/current_frame`.

The firmware must support the packed Spectra-6 format. The first successful render makes a 960000-byte frame available. `/api/current_image` remains a PNG. If port 8084 is already used on HAOS, change the host port in the add-on's Network settings and use that port in the firmware URL.

## Manual install (no GitHub access)

If HAOS can't reach GitHub, install from a local folder instead: run `python3 scripts/package_addon.py` in this repo to produce `dist/inkypi-neoframe-haos.tar.gz`, extract it, and copy the `inkypi_neoframe` folder over Samba into the `addons` share so the resulting path is `/addons/inkypi_neoframe/config.yaml`. It then appears under **Local add-ons** in the store; install it the same way as above.

## Storage and updates

Device settings, playlists, uploaded images, the current PNG/BIN and API keys live in Supervisor's persistent `/data` volume. They survive container replacement and are included in add-on backups. Configuration is managed in the InkyPi UI; there are no extra YAML options. Back up the add-on before uninstalling it.

Repository installs update like any other add-on: **Check for updates** in the store, then **Update** on the add-on's page. For a manual/local install, replace the add-on folder and use **Rebuild** from its menu instead. Either way `/data` is preserved — the startup script seeds defaults only when a persistent file or image directory does not yet exist.

The web UI is reachable both through Home Assistant's sidebar (Ingress, authenticated via your HA login) and directly on the configured LAN port (no HA login protection there — keep that port on your trusted LAN). The firmware's `/api/current_frame` polling always uses the direct port; it can't authenticate through Ingress. A small WSGI middleware (`src/utils/ingress_proxy.py`) rewrites InkyPi's root-relative `url_for()` links using Supervisor's `X-Ingress-Path` header so pages and assets resolve correctly under the sidebar panel.

## Scope and verification

The add-on needs no hardware devices, privileged mode, host networking, Docker socket or Supervisor API access. It uses the default protection settings. It renders remotely for the ESP32; no display attaches to the HAOS host.

The amd64 container is tested locally with Podman, including persistent data after replacement. Actual installation under Supervisor and the physical panel remain environment-specific checks. `aarch64` and `armv7` are declared but not build-tested — no ARM hardware or emulation was available to verify them before release; they're expected to mostly work since the base image and Python dependencies are multi-arch, but should be treated as unverified until confirmed on real hardware.

Reference: https://developers.home-assistant.io/docs/apps/tutorial/
