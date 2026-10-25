from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image
from utils.image_utils import take_screenshot, take_screenshot_with_storage
from urllib.parse import urlparse
import json
import logging

logger = logging.getLogger(__name__)

HA_TOKEN_KEY = "HOME_ASSISTANT_TOKEN"

def home_assistant_storage(url, token):
    """localStorage entry that logs the Home Assistant frontend in with a long-lived access token."""
    origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
    tokens = {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 1800,
        "hassUrl": origin,
        "clientId": f"{origin}/",
        # Long-lived tokens don't expire on the frontend's schedule; keep it from trying to refresh
        "expires": 4102444800000,
        "refresh_token": "",
    }
    return {"hassTokens": json.dumps(tokens)}

class Screenshot(BasePlugin):
    def generate_image(self, settings, device_config):

        url = settings.get('url')
        if not url:
            raise RuntimeError("URL is required.")

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        logger.info(f"Taking screenshot of url: {url}")

        if settings.get('homeAssistant') == "true":
            token = device_config.load_env_key(HA_TOKEN_KEY)
            if not token:
                raise RuntimeError(f"Home Assistant login needs {HA_TOKEN_KEY} on the API Keys page.")
            image = take_screenshot_with_storage(url, dimensions, home_assistant_storage(url, token), timeout_ms=40000)
        else:
            image = take_screenshot(url, dimensions, timeout_ms=40000)

        if not image:
            raise RuntimeError("Failed to take screenshot, please check logs.")

        return image
