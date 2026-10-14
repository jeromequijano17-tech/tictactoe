import unittest
from flask import Flask
from api import clean_name, create_api
from ratelimit import RateLimiter
from security import apply_security_headers
from tests.fakes import FakeRepo


def make(limit=10):
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test-secret", TESTING=True)
    repo = FakeRepo()
    app.register_blueprint(create_api(repo, RateLimiter(limit, 60)))
    apply_security_headers(app)
    return app, repo


class ApiTests(unittest.TestCase):
    def test_clean_name(self):
        self.assertEqual(clean_name("  Ann   Lee "), "Ann Lee")
        for bad in ("<script>alert(1)</script>", "A", "x" * 17, "", None, 5, "a'; DROP TABLE guests;--", "  "):
            self.assertIsNone(clean_name(bad), repr(bad))

    def test_guest_flow_sets_session(self):
        app, repo = make()
        c = app.test_client()
        self.assertEqual(c.get("/api/me").status_code, 401)
        self.assertEqual(c.get("/api/history").status_code, 401)
        r = c.post("/api/guest", json={"name": "Ann"})
        self.assertEqual((r.status_code, r.json), (200, {"name": "Ann"}))
        self.assertEqual(list(repo.guests.values()), ["Ann"])
        self.assertEqual(c.get("/api/me").json, {"name": "Ann"})
        self.assertEqual(c.get("/api/history").status_code, 200)
        c.post("/api/guest", json={"name": "Ann2"})
        self.assertEqual(len(repo.guests), 1)

    def test_bad_payloads_rejected(self):
        app, _ = make()
        c = app.test_client()
        self.assertEqual(c.post("/api/guest", json={"name": "<b>x</b>"}).status_code, 400)
        self.assertEqual(c.post("/api/guest", data="notjson").status_code, 400)
        self.assertEqual(c.post("/api/guest", json=["Ann"]).status_code, 400)

    def test_guest_rate_limit(self):
        app, _ = make(limit=3)
        c = app.test_client()
        codes = [c.post("/api/guest", json={"name": "Ann"}).status_code for _ in range(5)]
        self.assertEqual(codes, [200, 200, 200, 429, 429])

    def test_leaderboard_public_and_headers(self):
        app, _ = make()
        r = app.test_client().get("/api/leaderboard")
        self.assertEqual(r.status_code, 200)
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertIn("Strict-Transport-Security", r.headers)

    def test_ratelimiter_window(self):
        t = [0.0]
        rl = RateLimiter(2, 10, clock=lambda: t[0])
        self.assertEqual([rl.allow("k"), rl.allow("k"), rl.allow("k")], [True, True, False])
        t[0] = 11
        self.assertTrue(rl.allow("k"))
        self.assertTrue(rl.allow("other"))
