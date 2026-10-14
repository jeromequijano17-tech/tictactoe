def apply_security_headers(app, hsts=True):
    @app.after_request
    def _headers(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self' ws: wss:; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if hsts:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp
