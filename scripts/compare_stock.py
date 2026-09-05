"""Compare an already-final PNG with a captured stock BIN (contrast=1)."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PIL import Image
from display.neoframe_display import encode_frame

p = argparse.ArgumentParser()
p.add_argument("image")
p.add_argument("stock_bin")
a = p.parse_args()
actual = encode_frame(Image.open(a.image))
expected = Path(a.stock_bin).read_bytes()
if actual != expected:
    first = next(
        (i for i, (x, y) in enumerate(zip(actual, expected)) if x != y),
        min(len(actual), len(expected)),
    )
    raise SystemExit(
        f"MISMATCH at byte {first}; produced={len(actual)}, stock={len(expected)}"
    )
print(f"IDENTICAL: {len(actual)} bytes")
