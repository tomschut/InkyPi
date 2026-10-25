import requests
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from io import BytesIO
import os
import logging
import hashlib
import tempfile
import subprocess
import shutil
import base64
import json
import socket
import time
from urllib.parse import urlparse
import websocket

logger = logging.getLogger(__name__)

def get_image(image_url):
    response = requests.get(image_url, timeout=30)
    img = None
    if 200 <= response.status_code < 300 or response.status_code == 304:
        img = Image.open(BytesIO(response.content))
    else:
        logger.error(f"Received non-200 response from {image_url}: status_code: {response.status_code}")
    return img

def change_orientation(image, orientation, inverted=False):
    if orientation == 'horizontal':
        angle = 0
    elif orientation == 'vertical':
        angle = 90

    if inverted:
        angle = (angle + 180) % 360

    return image.rotate(angle, expand=1)

def resize_image(image, desired_size, image_settings=[]):
    img_width, img_height = image.size
    desired_width, desired_height = desired_size
    desired_width, desired_height = int(desired_width), int(desired_height)

    img_ratio = img_width / img_height
    desired_ratio = desired_width / desired_height

    keep_width = "keep-width" in image_settings

    x_offset, y_offset = 0,0
    new_width, new_height = img_width,img_height
    # Step 1: Determine crop dimensions
    desired_ratio = desired_width / desired_height
    if img_ratio > desired_ratio:
        # Image is wider than desired aspect ratio
        new_width = int(img_height * desired_ratio)
        if not keep_width:
            x_offset = (img_width - new_width) // 2
    else:
        # Image is taller than desired aspect ratio
        new_height = int(img_width / desired_ratio)
        if not keep_width:
            y_offset = (img_height - new_height) // 2

    # Step 2: Crop the image
    image = image.crop((x_offset, y_offset, x_offset + new_width, y_offset + new_height))

    # Step 3: Resize to the exact desired dimensions (if necessary)
    return image.resize((desired_width, desired_height), Image.LANCZOS)

def apply_image_enhancement(img, image_settings={}):
    # Convert image to RGB mode if necessary for enhancement operations
    # ImageEnhance requires RGB mode for operations like blend
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')

    # Each enhance() call blends over the full image, so skip factors of 1.0
    # (the no-op default) to avoid wasted full-frame passes on low-resource devices.
    enhancements = [
        (ImageEnhance.Brightness, image_settings.get("brightness", 1.0)),
        (ImageEnhance.Contrast, image_settings.get("contrast", 1.0)),
        (ImageEnhance.Color, image_settings.get("saturation", 1.0)),
        (ImageEnhance.Sharpness, image_settings.get("sharpness", 1.0)),
    ]
    for enhancer, factor in enhancements:
        if factor != 1.0:
            img = enhancer(img).enhance(factor)

    return img

def compute_image_hash(image):
    """Compute SHA-256 hash of an image."""
    image = image.convert("RGB")
    img_bytes = image.tobytes()
    return hashlib.sha256(img_bytes).hexdigest()

def take_screenshot_html(html_str, dimensions, timeout_ms=None):
    image = None
    try:
        # Create a temporary HTML file
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as html_file:
            html_file.write(html_str.encode("utf-8"))
            html_file_path = html_file.name

        image = take_screenshot(html_file_path, dimensions, timeout_ms)

        # Remove html file
        os.remove(html_file_path)

    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")

    return image

def _find_chromium_binary():
    """Find the first available Chromium-based binary in system PATH."""
    candidates = ["chromium-headless-shell", "chromium", "chrome"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            logger.debug(f"Found browser binary: {candidate} at {path}")
            return candidate
    return None


def take_screenshot(target, dimensions, timeout_ms=None):
    image = None
    try:
        # Find available browser binary
        browser = _find_chromium_binary()
        if not browser:
            logger.error("No Chromium-based browser found. Install chromium, chromium-headless-shell, or chrome.")
            return None

        # Create a temporary output file for the screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
            img_file_path = img_file.name

        command = [
            browser,
            target,
            "--headless",
            f"--screenshot={img_file_path}",
            f"--window-size={dimensions[0]},{dimensions[1]}",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--use-gl=swiftshader",
            "--hide-scrollbars",
            "--in-process-gpu",
            "--js-flags=--jitless",
            "--disable-zero-copy",
            "--disable-gpu-memory-buffer-compositor-resources",
            "--disable-extensions",
            "--disable-plugins",
            "--mute-audio",
            "--renderer-process-limit=1",
            "--no-zygote",
            "--no-sandbox"
        ]
        if timeout_ms:
            command.append(f"--timeout={timeout_ms}")
        result = subprocess.run(command, capture_output=True, check=False)

        # Check if the process failed or the output file is missing
        if result.returncode != 0 or not os.path.exists(img_file_path):
            stderr = result.stderr.decode(errors="replace").strip()[-2000:]
            logger.error(f"Failed to take screenshot (return code: {result.returncode})\n{stderr}")
            return None

        # Load the image using PIL
        with Image.open(img_file_path) as img:
            image = img.copy()

        # Remove image files
        os.remove(img_file_path)

    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")

    return image

def take_screenshot_with_storage(url, dimensions, local_storage, settle_ms=8000, timeout_ms=40000):
    """Screenshot a page that needs localStorage set before its scripts run (e.g. a Home Assistant login).

    Drives Chromium over the DevTools protocol. Keys are only written on the origin of `url`,
    so a redirect elsewhere never sees them.
    """
    browser = _find_chromium_binary()
    if not browser:
        logger.error("No Chromium-based browser found. Install chromium, chromium-headless-shell, or chrome.")
        return None

    origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
    seed = "".join(f"localStorage.setItem({json.dumps(k)}, {json.dumps(v)});" for k, v in local_storage.items())
    script = f"if (location.origin === {json.dumps(origin)}) {{ {seed} }}"

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    profile_dir = tempfile.mkdtemp(prefix="inkypi-chromium-")
    stderr_file = tempfile.TemporaryFile()
    proc = subprocess.Popen([
        browser, "--headless", f"--remote-debugging-port={port}", "--remote-allow-origins=*",
        f"--user-data-dir={profile_dir}", f"--window-size={dimensions[0]},{dimensions[1]}",
        "--disable-dev-shm-usage", "--disable-gpu", "--use-gl=swiftshader", "--hide-scrollbars",
        "--disable-extensions", "--mute-audio", "--no-zygote", "--no-sandbox", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=stderr_file)
    ws = None
    try:
        deadline = time.monotonic() + timeout_ms / 1000
        page = None
        while page is None:
            if proc.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Chromium DevTools did not start")
            try:
                targets = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=2).json()
                page = next((t for t in targets if t.get("type") == "page"), None)
            except requests.RequestException:
                pass
            if page is None:
                time.sleep(0.2)

        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=timeout_ms / 1000)
        next_id = iter(range(1, 1_000_000))

        def send(method, params=None):
            msg_id = next(next_id)
            ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
            return msg_id

        def wait_for(predicate):
            while time.monotonic() < deadline:
                msg = json.loads(ws.recv())
                if predicate(msg):
                    return msg
            raise RuntimeError(f"Timed out after {timeout_ms} ms loading {url}")

        send("Page.enable")
        send("Emulation.setDeviceMetricsOverride", {"width": dimensions[0], "height": dimensions[1], "deviceScaleFactor": 1, "mobile": False})
        send("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        nav_id = send("Page.navigate", {"url": url})
        nav = wait_for(lambda m: m.get("id") == nav_id)
        if nav.get("result", {}).get("errorText"):
            raise RuntimeError(f"Navigation to {url} failed: {nav['result']['errorText']}")
        wait_for(lambda m: m.get("method") == "Page.loadEventFired")
        # Single-page apps such as Home Assistant keep rendering after the load event
        time.sleep(settle_ms / 1000)
        shot_id = send("Page.captureScreenshot", {"format": "png"})
        shot = wait_for(lambda m: m.get("id") == shot_id)
        with Image.open(BytesIO(base64.b64decode(shot["result"]["data"]))) as img:
            return img.copy()
    except Exception as e:
        stderr_file.seek(0)
        stderr = stderr_file.read().decode(errors="replace").strip()[-2000:]
        logger.error(f"Failed to take screenshot of {url}: {e}\n{stderr}".rstrip())
        return None
    finally:
        if ws:
            ws.close()
        proc.kill()
        proc.wait()
        stderr_file.close()
        shutil.rmtree(profile_dir, ignore_errors=True)

def pad_image_blur(img: Image, dimensions: tuple[int, int]) -> Image:
    bkg = ImageOps.fit(img, dimensions)
    bkg = bkg.filter(ImageFilter.BoxBlur(8))
    img = ImageOps.contain(img, dimensions)

    img_size = img.size
    bkg.paste(img, ((dimensions[0] - img_size[0]) // 2, (dimensions[1] - img_size[1]) // 2))
    return bkg
