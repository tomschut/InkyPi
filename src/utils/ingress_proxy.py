"""Make url_for() Ingress-aware when Home Assistant Supervisor proxies this app.

Supervisor's Ingress proxy dispatches to this app with the ingress token
path already stripped from PATH_INFO, but sends the stripped prefix back
in X-Ingress-Path so a WSGI app can prepend it when generating links to
itself (root-relative url_for() output otherwise resolves, in the
browser, against the real origin -- outside the ingress path -- and 404s).
Outside Ingress this header is absent, so this is a no-op.
"""


class IngressPathMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        prefix = environ.get("HTTP_X_INGRESS_PATH")
        if prefix:
            environ["SCRIPT_NAME"] = prefix
        return self.wsgi_app(environ, start_response)
