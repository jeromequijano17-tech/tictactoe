import logging
import os
import re
from functools import wraps

from flask import Flask, request, session, render_template
from flask_socketio import SocketIO, emit, join_room as sio_join, leave_room as sio_leave
from werkzeug.middleware.proxy_fix import ProxyFix

from api import create_api
from config import Config
from db import MySQLRepo
from game_manager import GameError, GameManager
from ratelimit import RateLimiter
from security import apply_security_headers

CODE_RE = re.compile(r"^[A-Z0-9]{6}$")


def create_app(config=Config, repo=None):
    if not config.SECRET_KEY or config.SECRET_KEY == "change-me":
        raise RuntimeError("Set a strong SECRET_KEY in the environment")
    app = Flask(__name__)
    app.config.from_object(config)
    if config.TRUST_PROXY:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    apply_security_headers(app, hsts=config.SESSION_COOKIE_SECURE)

    repo = repo or MySQLRepo(config.DB_HOST, config.DB_PORT, config.DB_USER, config.DB_PASSWORD, config.DB_NAME)
    manager = GameManager(repo)
    app.register_blueprint(create_api(repo, RateLimiter(10, 60)))
    sock_limiter = RateLimiter(20, 5)
    connections = {}

    socketio = SocketIO(app, async_mode="threading", max_http_buffer_size=2000,
                        cors_allowed_origins=config.ALLOWED_ORIGINS or None)

    @app.get("/")
    def index():
        return render_template("index.html")

    def guarded(fn):
        @wraps(fn)
        def wrapper(data=None):
            conn = connections.get(request.sid)
            if not conn:
                return {"ok": False, "error": "Not connected"}
            if not sock_limiter.allow("sock:" + conn["guest"]["id"]):
                return {"ok": False, "error": "Slow down"}
            try:
                return fn(conn, data if isinstance(data, dict) else {})
            except GameError as e:
                return {"ok": False, "error": str(e)}
        return wrapper

    def enter(conn, state, seat):
        sio_join(state["code"])
        conn["code"] = state["code"]
        emit("state", state, to=state["code"])
        return {"ok": True, "code": state["code"], "seat": seat}

    @socketio.on("connect")
    def on_connect():
        if not session.get("gid"):
            return False  # reject: no guest session
        connections[request.sid] = {"guest": {"id": session["gid"], "name": session["name"]}, "code": None}

    @socketio.on("disconnect")
    def on_disconnect():
        conn = connections.pop(request.sid, None)
        if conn and conn["code"]:  # only the connection that entered the room can leave it
            state = manager.leave(conn["guest"]["id"])
            if state:
                socketio.emit("state", state, to=conn["code"])

    @socketio.on("create_room")
    @guarded
    def create_room(conn, data):
        return enter(conn, *manager.create_room(conn["guest"]))

    @socketio.on("quick_match")
    @guarded
    def quick_match(conn, data):
        return enter(conn, *manager.quick_match(conn["guest"]))

    @socketio.on("join")
    @guarded
    def join(conn, data):
        code = str(data.get("code", "")).strip().upper()
        if not CODE_RE.match(code):
            raise GameError("Invalid room code")
        return enter(conn, *manager.join_room(code, conn["guest"]))

    @socketio.on("move")
    @guarded
    def move(conn, data):
        state = manager.play(conn["guest"]["id"], data.get("index"))
        emit("state", state, to=state["code"])
        return {"ok": True}

    @socketio.on("rematch")
    @guarded
    def rematch(conn, data):
        state = manager.rematch(conn["guest"]["id"])
        emit("state", state, to=state["code"])
        return {"ok": True}

    @socketio.on("leave_room")
    @guarded
    def leave(conn, data):
        code = conn["code"]
        if code:
            state = manager.leave(conn["guest"]["id"])
            sio_leave(code)
            conn["code"] = None
            if state:
                emit("state", state, to=code)
        return {"ok": True}

    return app, socketio


logging.basicConfig(level=logging.INFO)
app, socketio = create_app()

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
