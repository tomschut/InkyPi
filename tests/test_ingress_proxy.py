import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from utils.ingress_proxy import IngressPathMiddleware


def wsgi_app(environ, start_response):
    start_response("200 OK", [])
    return [environ.get("SCRIPT_NAME", "").encode()]


def call(environ):
    return b"".join(IngressPathMiddleware(wsgi_app)(environ, lambda *a: None)).decode()


def test_sets_script_name_from_ingress_header():
    assert call({"HTTP_X_INGRESS_PATH": "/api/hassio_ingress/token123"}) == "/api/hassio_ingress/token123"


def test_no_op_without_ingress_header():
    assert call({}) == ""
