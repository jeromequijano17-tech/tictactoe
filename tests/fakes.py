class FakeRepo:
    def __init__(self):
        self.guests, self.matches, self.fail = {}, [], False

    def upsert_guest(self, gid, name):
        self.guests[gid] = name

    def save_match(self, x, o, winner, result, moves):
        if self.fail:
            raise RuntimeError("db down")
        self.matches.append((x, o, winner, result, moves))
        return len(self.matches)

    def leaderboard(self, limit=20):
        return [{"name": "A", "wins": 1, "losses": 0, "draws": 0, "played": 1, "points": 3}]

    def history(self, gid, limit=20):
        return [{"id": 1, "opponent": "B", "outcome": "win", "result": "win", "played_at": "2026-01-01 00:00"}]
