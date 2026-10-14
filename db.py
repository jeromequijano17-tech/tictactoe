"""MySQL repository. All queries are parameterized (no string-built SQL)."""
import pymysql
import pymysql.cursors


class MySQLRepo:
    def __init__(self, host, port, user, password, name):
        self.cfg = dict(host=host, port=port, user=user, password=password, database=name,
                        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                        autocommit=True, connect_timeout=5)

    def _conn(self):
        return pymysql.connect(**self.cfg)

    def upsert_guest(self, gid, name):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("INSERT INTO guests (id, name) VALUES (%s, %s) "
                        "ON DUPLICATE KEY UPDATE name = VALUES(name)", (gid, name))

    def save_match(self, x_id, o_id, winner_id, result, moves):
        with self._conn() as c, c.cursor() as cur:
            cur.execute("INSERT INTO matches (player_x, player_o, winner_id, result, moves) "
                        "VALUES (%s, %s, %s, %s, %s)", (x_id, o_id, winner_id, result, moves))
            return cur.lastrowid

    def leaderboard(self, limit=20):
        sql = ("SELECT * FROM (SELECT g.name, "
               "SUM(m.winner_id = g.id) AS wins, "
               "SUM(m.winner_id IS NOT NULL AND m.winner_id <> g.id) AS losses, "
               "SUM(m.winner_id IS NULL) AS draws, COUNT(*) AS played "
               "FROM guests g JOIN matches m ON g.id IN (m.player_x, m.player_o) "
               "GROUP BY g.id, g.name) t "
               "ORDER BY (wins * 3 + draws) DESC, wins DESC, played ASC LIMIT %s")
        with self._conn() as c, c.cursor() as cur:
            cur.execute(sql, (int(limit),))
            return [{"name": r["name"], "wins": int(r["wins"]), "losses": int(r["losses"]),
                     "draws": int(r["draws"]), "played": int(r["played"]),
                     "points": int(r["wins"]) * 3 + int(r["draws"])} for r in cur.fetchall()]

    def history(self, gid, limit=20):
        sql = ("SELECT m.id, m.played_at, m.winner_id, m.result, m.player_x, gx.name AS xn, go.name AS onm "
               "FROM matches m JOIN guests gx ON gx.id = m.player_x JOIN guests go ON go.id = m.player_o "
               "WHERE %s IN (m.player_x, m.player_o) ORDER BY m.id DESC LIMIT %s")
        with self._conn() as c, c.cursor() as cur:
            cur.execute(sql, (gid, int(limit)))
            out = []
            for r in cur.fetchall():
                opp = r["onm"] if r["player_x"] == gid else r["xn"]
                outcome = "draw" if r["winner_id"] is None else ("win" if r["winner_id"] == gid else "loss")
                out.append({"id": r["id"], "opponent": opp, "outcome": outcome, "result": r["result"],
                            "played_at": r["played_at"].strftime("%Y-%m-%d %H:%M")})
            return out
