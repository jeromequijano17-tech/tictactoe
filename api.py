import re
import uuid

from flask import Blueprint, jsonify, request, session

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{1,15}$")


def clean_name(raw):
    if not isinstance(raw, str):
        return None
    name = " ".join(raw.split())
    return name if NAME_RE.match(name) else None


def create_api(repo, limiter):
    bp = Blueprint("api", __name__)

    @bp.get("/healthz")
    def health():
        return jsonify(ok=True)

    @bp.post("/api/guest")
    def guest():
        if not limiter.allow("guest:" + (request.remote_addr or "?")):
            return jsonify(error="Too many requests"), 429
        data = request.get_json(silent=True)
        name = clean_name(data.get("name") if isinstance(data, dict) else None)
        if not name:
            return jsonify(error="Name: 2-16 chars, letters/numbers/space/_/- only"), 400
        gid = session.get("gid") or uuid.uuid4().hex
        repo.upsert_guest(gid, name)
        session["gid"], session["name"] = gid, name
        session.permanent = True
        return jsonify(name=name)

    @bp.get("/api/me")
    def me():
        if not session.get("gid"):
            return jsonify(error="No guest session"), 401
        return jsonify(name=session["name"])

    @bp.get("/api/leaderboard")
    def leaderboard():
        return jsonify(repo.leaderboard(20))

    @bp.get("/api/history")
    def history():
        if not session.get("gid"):
            return jsonify(error="No guest session"), 401
        return jsonify(repo.history(session["gid"], 20))

    return bp
