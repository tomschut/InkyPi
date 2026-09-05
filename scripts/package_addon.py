"""Regenerate the offline-install archive for the Home Assistant OS add-on.

inkypi_neoframe/ is self-contained (its Dockerfile clones this fork directly),
so there is nothing to sync into it -- this just archives it for the offline
install path documented in inkypi_neoframe/DOCS.md.
"""
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
addon = root / "inkypi_neoframe"
(root / "dist").mkdir(exist_ok=True)
with tarfile.open(root / "dist/inkypi-neoframe-haos.tar.gz", "w:gz") as archive:
    for path in sorted(addon.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            archive.add(path, arcname=path.relative_to(root))
print("Created dist/inkypi-neoframe-haos.tar.gz")
