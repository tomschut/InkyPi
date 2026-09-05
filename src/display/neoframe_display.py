"""Spectra-6 port of deftdawg/neoframe src/algorithms.ts; see REFERENCES.md."""

import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from functools import lru_cache
from PIL import Image
from display.abstract_display import AbstractDisplay

logger = logging.getLogger(__name__)
PALETTE = (
    (255, 255, 0),
    (41, 204, 20),
    (0, 0, 255),
    (255, 0, 0),
    (0, 0, 0),
    (255, 255, 255),
)
CODES = (2, 6, 5, 3, 0, 1)


def lab(r, g, b):
    r, g, b = (
        100
        * (((v / 255 + 0.055) / 1.055) ** 2.4 if v / 255 > 0.04045 else v / 255 / 12.92)
        for v in (r, g, b)
    )
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 95.047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722) / 100.0
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 108.883
    x, y, z = (
        v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116 for v in (x, y, z)
    )
    return 116 * y - 16, 500 * (x - y), 200 * (y - z)


LAB_PALETTE = tuple(lab(*c) for c in PALETTE)


@lru_cache(maxsize=65536)
def closest(r, g, b):
    if r < 50 and g < 150 and b > 100:
        return 2
    l, a, bl = lab(r, g, b)
    # Stable minimum preserves the reference's palette tie order.
    return min(
        range(6),
        key=lambda i: (
            (
                0.2 * (l - LAB_PALETTE[i][0]) ** 2
                + 3 * (a - LAB_PALETTE[i][1]) ** 2
                + 3 * (bl - LAB_PALETTE[i][2]) ** 2
            )
            ** 0.5
        ),
    )


def encode_frame(image):
    """Reference Floyd–Steinberg, strength 1; input already enhanced by InkyPi.

    Uint8ClampedArray uses ties-to-even rounding after EACH error update.
    No second contrast adjustment, scaling, rotation, header or padding.
    """
    width, height = image.size
    if width % 2 or width < 2 or height < 1:
        raise ValueError("Frame must have positive dimensions and even width")
    data = bytearray(image.convert("RGB").tobytes())
    result = bytearray(width * height // 2)
    for y in range(height):
        for x in range(width):
            idx = (y * width + x) * 3
            rgb = data[idx : idx + 3]
            color = closest(*rgb)
            code = CODES[color]
            pos = (y * width + x) // 2
            if x % 2:
                result[pos] |= code
            else:
                result[pos] = code << 4
            error = tuple(rgb[c] - PALETTE[color][c] for c in range(3))
            neighbors = []
            if x + 1 < width:
                neighbors.append((idx + 3, 7))
            if y + 1 < height:
                if x > 0:
                    neighbors.append((idx + width * 3 - 3, 3))
                neighbors.append((idx + width * 3, 5))
                if x + 1 < width:
                    neighbors.append((idx + width * 3 + 3, 1))
            for target, weight in neighbors:
                for c in range(3):
                    data[target + c] = round(
                        min(255, max(0, data[target + c] + error[c] * weight / 16))
                    )
    return bytes(result)


_PALETTE_INDEX = {code: i for i, code in enumerate(CODES)}
_HI_NIBBLE_INDEX = bytes(_PALETTE_INDEX.get(b >> 4, 0) for b in range(256))
_LO_NIBBLE_INDEX = bytes(_PALETTE_INDEX.get(b & 15, 0) for b in range(256))


def decode_frame(data, width, height):
    """Inverse of encode_frame: reconstruct an RGB image from packed nibbles."""
    expected = width * height // 2
    if len(data) != expected:
        raise ValueError(f"Expected {expected} bytes for {width}x{height}, got {len(data)}")
    indices = bytearray(width * height)
    indices[0::2] = data.translate(_HI_NIBBLE_INDEX)
    indices[1::2] = data.translate(_LO_NIBBLE_INDEX)
    image = Image.frombytes("P", (width, height), bytes(indices))
    image.putpalette([channel for rgb in PALETTE for channel in rgb])
    return image.convert("RGB")


VALID_PANEL_ROTATIONS = (90, 270)


def render_preview(data, rotation=90):
    """Packed bytes reconstructed as the mounted panel will display them.

    Inverse of the `rotation`-degree counter-clockwise pre-rotation
    NeoFrameDisplay.display_image() applies before packing.
    """
    return decode_frame(data, 1200, 1600).rotate(-rotation, expand=True)


class NeoFrameDisplay(AbstractDisplay):
    def initialize_display(self):
        self.path = Path(self.device_config.current_image_file).with_name(
            "current_frame.bin"
        )
        self.lock = threading.Lock()

    def display_image(self, image, image_settings=None):
        temporary = None
        try:
            with self.lock:
                if image.size != (1600, 1200):
                    raise ValueError(
                        f"Expected final 1600x1200 frame, got {image.size}"
                    )
                rotation = self.device_config.get_config("panel_rotation", 90)
                if rotation not in VALID_PANEL_ROTATIONS:
                    raise ValueError(
                        f"panel_rotation must be one of {VALID_PANEL_ROTATIONS}, got {rotation!r}"
                    )
                # The panel's native raster is fixed at 1200x1600 (firmware has no
                # rotation of its own), so only a 90/270 pre-rotation of our fixed
                # 1600x1200 composition produces a matching shape; 0/180 cannot.
                # `rotation` is the panel's clockwise mounting angle in its
                # enclosure; PIL's positive (counter-clockwise) rotate by that same
                # value is the compensating transform that lands content upright.
                packed = encode_frame(image.rotate(rotation, expand=True))
                try:
                    if self.path.read_bytes() == packed:
                        return
                    previous = int(self.path.stat().st_mtime)
                except FileNotFoundError:
                    previous = 0
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    dir=self.path.parent, prefix=".frame-", delete=False
                ) as f:
                    temporary = f.name
                    f.write(packed)
                    f.flush()
                    os.fsync(f.fileno())
                # Distinct changed frames must not share an HTTP-second validator.
                stamp = max(int(time.time()), previous + 1)
                os.utime(temporary, (stamp, stamp))
                os.replace(temporary, self.path)
                temporary = None
        except Exception:
            logger.exception("NeoFrame generation failed; keeping previous frame")
        finally:
            if temporary:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    logger.exception("Could not remove temporary NeoFrame file")
