# Validation — 2026-09-05

- Six pytest cases passed in 21.49 seconds: original TypeScript byte parity at 6×1, 64×48 and 1600×1200; palette/nibble order; atomic publication and HTTP behavior; actual upstream manager and original PNG route integration.
- Full-frame output: 960000 bytes. Both implementations produced SHA-256 `cca6f3aab25e5b8137758df05c5c1dac4fb4faea19b22a4c43fe6259abec8b5c`. Python encoding took 11.74 seconds on this host.
- Original TypeScript ran directly under Node 24.19.0, without rewriting its algorithm. Inputs and matching outputs are retained in artifacts/ (ignored by version control).
- Container built successfully using Podman, Python 3.13 and upstream pinned requirements. Docker CLI was unavailable; Compose itself was not executed.
- Temporary container started the actual InkyPi server, rendered the startup image, served a 960000-byte BIN and the PNG, and returned 304 to If-Modified-Since. The temporary container was removed after testing.
- After hardening cleanup-error handling, the three affected palette/publication/integration cases were rerun and the final image rebuilt.

M1 and M2 pass locally. Reference-source parity passes. M3 still needs a BIN captured from the working stock pipeline for the same final input, using scripts/compare_stock.py. M4 still needs Project 1 firmware and the physical panel. No physical acceptance is claimed.

Changed output uses a monotonically increasing whole-second mtime; identical packed output preserves its timestamp. Rapid changes or a backwards system clock can place the validator ahead of wall-clock time. ETags identify exact payloads. The writer lock serializes this backend instance, matching upstream's single process deployment.

## HAOS add-on package

- Built `inkypi-neoframe-haos:0.1.0` successfully with Podman on amd64.
- Two additional tests passed for persistent storage initialization/replacement and self-contained archive contents.
- Live add-on test on port 18084 passed: UI/PNG/BIN 200, 960000-byte BIN, Last-Modified and ETag conditional 304.
- Replaced the container with the same /data volume: device settings, API-key file, uploaded-image marker, packed frame and ETag survived.
- The Podman test uses `--init` to match HAOS's enabled init and `:Z` on its private test volume so SELinux permits the replacement container. SELinux was not disabled. Test container and volume were removed after success.
- Install archive: dist/inkypi-neoframe-haos.tar.gz. Instructions: inkypi_neoframe/DOCS.md.
- Not yet installed under an actual Home Assistant Supervisor; only amd64 is advertised. Physical frame validation remains pending.
