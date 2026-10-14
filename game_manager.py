"""Server-authoritative game/room state. Independent of Flask/SocketIO/MySQL (repo is injected)."""
import logging
import secrets
import threading

from game_logic import check_winner, is_full, new_board

log = logging.getLogger(__name__)
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
OTHER = {"X": "O", "O": "X"}


class GameError(Exception):
    pass


class Room:
    def __init__(self, code):
        self.code = code
        self.players = {}          # symbol -> {"id","name","seat"}
        self.board = new_board()
        self.turn = "X"
        self.status = "waiting"    # waiting | playing | finished
        self.winner = self.line = self.result = None
        self.wins = {}             # guest id -> wins in this room
        self.draws = 0
        self.rematch = set()
        self.opponent_left = False
        self.moves = []
        self.round = 1

    def symbol_of(self, gid):
        for s, p in self.players.items():
            if p["id"] == gid:
                return s
        return None

    def public(self):
        """Never exposes guest ids."""
        return {
            "code": self.code, "board": list(self.board), "turn": self.turn, "status": self.status,
            "round": self.round, "winner": self.winner, "line": self.line, "result": self.result,
            "opponent_left": self.opponent_left, "draws": self.draws,
            "players": {s: {"name": p["name"], "seat": p["seat"]} for s, p in self.players.items()},
            "scores": {str(p["seat"]): self.wins.get(p["id"], 0) for p in self.players.values()},
            "rematch": [p["seat"] for p in self.players.values() if p["id"] in self.rematch],
        }


class GameManager:
    def __init__(self, repo, max_rooms=1000):
        self.repo, self.max_rooms = repo, max_rooms
        self.rooms, self.by_guest, self.waiting = {}, {}, None
        self.lock = threading.RLock()

    def room_of(self, gid):
        return self.by_guest.get(gid)

    def _free(self, guest):
        if guest["id"] in self.by_guest:
            raise GameError("You are already in a game (another tab?)")
        if len(self.rooms) >= self.max_rooms:
            raise GameError("Server is busy, try again later")

    def _new_room(self, guest):
        while True:
            code = "".join(secrets.choice(ALPHABET) for _ in range(6))
            if code not in self.rooms:
                break
        room = Room(code)
        room.players["X"] = {"id": guest["id"], "name": guest["name"], "seat": 1}
        self.rooms[code] = room
        self.by_guest[guest["id"]] = code
        return room

    def create_room(self, guest):
        with self.lock:
            self._free(guest)
            return self._new_room(guest).public(), 1

    def _join(self, room, guest):
        room.players["O"] = {"id": guest["id"], "name": guest["name"], "seat": 2}
        room.status = "playing"
        self.by_guest[guest["id"]] = room.code
        return room.public(), 2

    def join_room(self, code, guest):
        with self.lock:
            self._free(guest)
            room = self.rooms.get(code)
            if not room:
                raise GameError("Room not found")
            if room.status != "waiting" or len(room.players) != 1:
                raise GameError("Room is full")
            if self.waiting == code:
                self.waiting = None
            return self._join(room, guest)

    def quick_match(self, guest):
        with self.lock:
            self._free(guest)
            room = self.rooms.get(self.waiting) if self.waiting else None
            if room and room.status == "waiting" and len(room.players) == 1:
                self.waiting = None
                return self._join(room, guest)
            room = self._new_room(guest)
            self.waiting = room.code
            return room.public(), 1

    def _finish(self, room, winner_sym, line, result):
        room.status, room.winner, room.line, room.result = "finished", winner_sym, line, result
        wid = None
        if winner_sym:
            wid = room.players[winner_sym]["id"]
            room.wins[wid] = room.wins.get(wid, 0) + 1
        else:
            room.draws += 1
        try:
            self.repo.save_match(room.players["X"]["id"], room.players["O"]["id"], wid,
                                 result, ",".join(map(str, room.moves)))
        except Exception:
            log.exception("Could not save match")  # game continues even if DB is down

    def play(self, gid, idx):
        with self.lock:
            room = self.rooms.get(self.by_guest.get(gid))
            if not room:
                raise GameError("You are not in a game")
            sym = room.symbol_of(gid)
            if room.status != "playing":
                raise GameError("Game is not active")
            if sym != room.turn:
                raise GameError("Not your turn")
            if type(idx) is not int or not 0 <= idx <= 8:
                raise GameError("Invalid cell")
            if room.board[idx]:
                raise GameError("Cell already taken")
            room.board[idx] = sym
            room.moves.append(idx)
            w, line = check_winner(room.board)
            if w:
                self._finish(room, w, line, "win")
            elif is_full(room.board):
                self._finish(room, None, None, "draw")
            else:
                room.turn = OTHER[sym]
            return room.public()

    def rematch(self, gid):
        with self.lock:
            room = self.rooms.get(self.by_guest.get(gid))
            if not room:
                raise GameError("You are not in a game")
            if room.status != "finished" or room.opponent_left or len(room.players) != 2:
                raise GameError("Rematch not available")
            room.rematch.add(gid)
            if len(room.rematch) == 2:
                room.players = {"X": room.players["O"], "O": room.players["X"]}  # swap sides
                room.board, room.moves, room.turn = new_board(), [], "X"
                room.status, room.winner, room.line, room.result = "playing", None, None, None
                room.rematch.clear()
                room.round += 1
            return room.public()

    def leave(self, gid):
        """Leave/disconnect. Forfeits an active game. Returns remaining room state or None."""
        with self.lock:
            code = self.by_guest.pop(gid, None)
            room = self.rooms.get(code)
            if not room:
                return None
            sym = room.symbol_of(gid)
            if room.status == "playing" and sym:
                self._finish(room, OTHER[sym], None, "forfeit")
            room.players.pop(sym, None)
            room.rematch.clear()
            if not room.players:
                del self.rooms[code]
                if self.waiting == code:
                    self.waiting = None
                return None
            room.opponent_left = True
            return room.public()
