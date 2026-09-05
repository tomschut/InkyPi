import hashlib
from io import BytesIO
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from display import neoframe_display as backend
from display.display_manager import DisplayManager
from blueprints.main import main_bp
from blueprints.frame import frame_bp
from blueprints.settings import settings_bp


@pytest.mark.parametrize("size", [(6, 1), (64, 48), (1600, 1200)])
def test_original_typescript_parity(tmp_path, size):
    source = ROOT / ".reference/neoframe-src/src/algorithms.ts"
    assert source.exists(), "Fetch pinned reference per NEOFRAME.md"
    rng = random.Random(184)
    if size == (1600, 1200):
        image = Image.new("RGB", size)
        # Full-size gradients exercise row boundaries and every nibble position.
        image.putdata(
            [
                ((x * 255) // 1599, (y * 255) // 1199, ((x + y) * 19) % 256)
                for y in range(1200)
                for x in range(1600)
            ]
        )
    else:
        image = Image.frombytes("RGB", size, rng.randbytes(size[0] * size[1] * 3))
    image.save(tmp_path / "input.png")
    (tmp_path / "input.rgba").write_bytes(image.convert("RGBA").tobytes())
    runner = tmp_path / "reference.mjs"
    runner.write_text(
        """import {readFileSync,writeFileSync} from 'node:fs';
import {ditherImage,processImageData} from '"""
        + source.as_uri()
        + """';
const image={width:Number(process.argv[2]),height:Number(process.argv[3]),data:new Uint8ClampedArray(readFileSync(process.argv[4]))};
const config={ditherType:'floydSteinberg',ditherStrength:'1',ditherMode:'sixColor'};
ditherImage(image,config);
writeFileSync(process.argv[5],processImageData(image,config));
"""
    )
    expected = tmp_path / "stock-reference.bin"
    subprocess.run(
        [
            str(ROOT / ".venv/bin/node"),
            str(runner),
            str(size[0]),
            str(size[1]),
            str(tmp_path / "input.rgba"),
            str(expected),
        ],
        check=True,
    )
    start = time.monotonic()
    actual = backend.encode_frame(image)
    assert actual == expected.read_bytes()
    print(
        f"Parity {size}: {len(actual)} bytes, Python {time.monotonic() - start:.2f}s, SHA256 {hashlib.sha256(actual).hexdigest()}"
    )
    if size == (1600, 1200):
        out = ROOT / "artifacts"
        out.mkdir(exist_ok=True)
        shutil.copy2(tmp_path / "input.png", out / "reference-input.png")
        shutil.copy2(expected, out / "reference.bin")
        (out / "python.bin").write_bytes(actual)


def test_palette_order():
    image = Image.new("RGB", (6, 1))
    image.putdata(backend.PALETTE)
    assert backend.encode_frame(image) == bytes.fromhex("26 53 01")


@pytest.fixture
def setup(tmp_path):
    config = SimpleNamespace(
        current_image_file=str(tmp_path / "current_image.png"),
        get_config=lambda key, default=None: default,
    )
    display = backend.NeoFrameDisplay(config)
    app = Flask(__name__)
    app.config["DEVICE_CONFIG"] = config
    app.register_blueprint(frame_bp)
    return display, app.test_client()


def test_publication_and_http(setup, monkeypatch):
    display, client = setup
    assert client.get("/api/current_frame").status_code == 404
    payload = b"\x12" * 960000
    monkeypatch.setattr(backend, "encode_frame", lambda image: payload)
    monkeypatch.setattr(backend.time, "time", lambda: 1700000000)
    image = Image.new("RGB", (1600, 1200))
    display.display_image(image)
    first = client.get("/api/current_frame")
    assert first.status_code == 200 and first.data == payload
    assert first.mimetype == "application/octet-stream"
    assert first.headers["Cache-Control"] == "no-cache"
    stamp = display.path.stat().st_mtime_ns
    display.display_image(image)
    assert display.path.stat().st_mtime_ns == stamp
    assert (
        client.get(
            "/api/current_frame",
            headers={"If-Modified-Since": first.headers["Last-Modified"]},
        ).status_code
        == 304
    )
    assert (
        client.get(
            "/api/current_frame", headers={"If-None-Match": first.headers["ETag"]}
        ).status_code
        == 304
    )
    assert (
        client.get(
            "/api/current_frame", headers={"If-Modified-Since": "garbage"}
        ).status_code
        == 200
    )
    assert client.head("/api/current_frame").data == b""
    payload = b"\x56" * 960000
    display.display_image(image)
    changed = client.get(
        "/api/current_frame",
        headers={"If-Modified-Since": first.headers["Last-Modified"]},
    )
    assert changed.status_code == 200 and changed.data == payload
    assert changed.headers["Last-Modified"] != first.headers["Last-Modified"]
    assert changed.headers["ETag"] != first.headers["ETag"]
    # ETag takes precedence over an old timestamp.
    assert (
        client.get(
            "/api/current_frame",
            headers={
                "If-None-Match": changed.headers["ETag"],
                "If-Modified-Since": first.headers["Last-Modified"],
            },
        ).status_code
        == 304
    )
    previous = display.path.read_bytes()

    def fail(*args):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(backend.os, "replace", fail)
    display.display_image(image)
    assert display.path.read_bytes() == previous
    assert not list(display.path.parent.glob(".frame-*"))
    display.display_image(Image.new("RGB", (8, 8)))
    assert display.path.read_bytes() == previous


def test_decode_frame_round_trip():
    image = Image.new("RGB", (1200, 1600), "white")
    image.paste("black", (0, 0, 1200, 800))
    decoded = backend.decode_frame(backend.encode_frame(image), 1200, 1600)
    assert decoded.getpixel((0, 0)) == (0, 0, 0)
    assert decoded.getpixel((0, 1599)) == (255, 255, 255)
    with pytest.raises(ValueError):
        backend.decode_frame(b"\x00" * 10, 1200, 1600)


def test_preview_query_param(setup):
    display, client = setup
    image = Image.new("RGB", (1600, 1200), "white")
    image.paste("black", (0, 0, 800, 1200))
    display.display_image(image)
    preview = client.get("/api/current_frame?preview")
    assert preview.status_code == 200 and preview.mimetype == "image/png"
    rendered = Image.open(BytesIO(preview.data))
    assert rendered.size == (1600, 1200)
    # display_image() and the preview route both default to panel_rotation 90
    # (the same fixture config), so packing then un-rotating is a round trip:
    # the preview should reproduce exactly what was sent (no quantization
    # error for pure palette colors), regardless of the rotation's direction.
    assert rendered.convert("RGB").tobytes() == image.tobytes()
    assert client.get("/api/current_frame").mimetype == "application/octet-stream"


class _Config:
    """Minimal device_config stand-in: real display_manager.py/settings.py, fake storage."""

    def __init__(self, **overrides):
        self.current_image_file = overrides.pop(
            "current_image_file", "src/static/images/current_image.png"
        )
        self.config = {
            "display_type": "neoframe",
            "orientation": "horizontal",
            "inverted_image": False,
            "panel_rotation": 90,
            "image_settings": {},
        }
        self.config.update(overrides)

    def get_resolution(self):
        return (1600, 1200)

    def get_config(self, key=None, default=None):
        return self.config.get(key, default) if key is not None else self.config

    def update_config(self, updates):
        self.config.update(updates)


def test_real_display_manager_and_routes(tmp_path):
    # No copying, no patch script: display_manager.py and frame_bp are the
    # real, unmodified-except-for-two-lines upstream files, imported directly.
    c = _Config(current_image_file=str(tmp_path / "current_image.png"))
    Path(c.current_image_file).parent.mkdir(parents=True, exist_ok=True)
    m = DisplayManager(c)
    assert isinstance(m.display, backend.NeoFrameDisplay)
    img = Image.new("RGB", (1600, 1200), "white")
    img.paste("black", (0, 0, 800, 1200))
    m.display_image(img)
    assert Image.open(c.current_image_file).tobytes() == img.tobytes()
    packed = Path(c.current_image_file).with_name("current_frame.bin").read_bytes()
    # ../neoframe's firmware always expects its fixed native 1200x1600 raster (no
    # header, no rotation of its own), so NeoFrameDisplay rotates the plain
    # 1600x1200 composition by panel_rotation degrees (here 90) before packing.
    # Left/right halves land as bottom/top: native row 0 (bin[0:600]) comes from
    # the composition's right (white) edge, native row 1599 from its left (black).
    assert len(packed) == 960000
    assert packed[0] == 0x11 and packed[479999] == 0x11
    assert packed[480000] == 0x00 and packed[959999] == 0x00

    # main_bp registers alongside frame_bp without conflict, same as inkypi.py.
    # (main_bp's /api/current_image hardcodes a path relative to the real
    # source tree rather than device_config, so it isn't exercised here.)
    app = Flask(__name__)
    app.config["DEVICE_CONFIG"] = c
    app.register_blueprint(main_bp)
    app.register_blueprint(frame_bp)
    client = app.test_client()
    assert client.get("/api/current_frame").data == packed


def test_settings_page_panel_rotation(tmp_path):
    c = _Config(current_image_file=str(tmp_path / "current_image.png"))
    app = Flask(__name__, template_folder=str(ROOT / "src/templates"))
    app.config["DEVICE_CONFIG"] = c
    app.register_blueprint(settings_bp)
    client = app.test_client()
    page = client.get("/settings")
    assert page.status_code == 200
    assert b"panelRotation" in page.data and b"clockwise" in page.data

    # A non-neoframe display type must not show or accept the field.
    c.config["display_type"] = "inky"
    other = client.get("/settings")
    assert b"panelRotation" not in other.data
