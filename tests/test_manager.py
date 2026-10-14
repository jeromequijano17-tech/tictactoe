import unittest
from game_manager import GameError, GameManager
from tests.fakes import FakeRepo

A = {"id": "a" * 32, "name": "Ann"}
B = {"id": "b" * 32, "name": "Bob"}
C = {"id": "c" * 32, "name": "Cy"}
WIN_X = [(A, 0), (B, 3), (A, 1), (B, 4), (A, 2)]


def started():
    repo = FakeRepo()
    m = GameManager(repo)
    s, _ = m.create_room(A)
    m.join_room(s["code"], B)
    return m, repo


def play(m, seq):
    st = None
    for g, i in seq:
        st = m.play(g["id"], i)
    return st


class ManagerTests(unittest.TestCase):
    def test_create_join_starts_game(self):
        m = GameManager(FakeRepo())
        s, seat = m.create_room(A)
        self.assertEqual((s["status"], seat), ("waiting", 1))
        s, seat = m.join_room(s["code"], B)
        self.assertEqual((s["status"], seat, s["turn"]), ("playing", 2, "X"))

    def test_public_state_hides_guest_ids(self):
        m, _ = started()
        self.assertNotIn("a" * 32, str(m.rooms[m.room_of(A["id"])].public()))

    def test_join_errors(self):
        m, _ = started()
        with self.assertRaises(GameError): m.join_room(m.room_of(A["id"]), C)
        with self.assertRaises(GameError): m.join_room("ZZZZZZ", C)

    def test_cannot_join_own_room_or_two_rooms(self):
        m = GameManager(FakeRepo())
        s, _ = m.create_room(A)
        with self.assertRaises(GameError): m.join_room(s["code"], A)
        with self.assertRaises(GameError): m.create_room(A)

    def test_turn_order_and_taken_cell(self):
        m, _ = started()
        with self.assertRaises(GameError): m.play(B["id"], 0)
        m.play(A["id"], 4)
        with self.assertRaises(GameError): m.play(A["id"], 0)
        with self.assertRaises(GameError): m.play(B["id"], 4)

    def test_invalid_indexes(self):
        m, _ = started()
        for bad in (-1, 9, "1", None, 1.0, True, [1]):
            with self.assertRaises(GameError, msg=repr(bad)): m.play(A["id"], bad)

    def test_non_player_cannot_move(self):
        m, _ = started()
        with self.assertRaises(GameError): m.play(C["id"], 0)

    def test_win_saved_and_locks_board(self):
        m, repo = started()
        st = play(m, WIN_X)
        self.assertEqual((st["status"], st["winner"], st["line"]), ("finished", "X", [0, 1, 2]))
        self.assertEqual(repo.matches, [(A["id"], B["id"], A["id"], "win", "0,3,1,4,2")])
        self.assertEqual(st["scores"], {"1": 1, "2": 0})
        with self.assertRaises(GameError): m.play(B["id"], 5)

    def test_draw(self):
        m, repo = started()
        st = play(m, [(A, 0), (B, 1), (A, 2), (B, 4), (A, 3), (B, 5), (A, 7), (B, 6), (A, 8)])
        self.assertEqual((st["status"], st["winner"], st["result"], st["draws"]), ("finished", None, "draw", 1))
        self.assertIsNone(repo.matches[0][2])

    def test_rematch_needs_both_swaps_sides_keeps_score(self):
        m, _ = started()
        play(m, WIN_X)
        st = m.rematch(A["id"])
        self.assertEqual((st["status"], st["rematch"]), ("finished", [1]))
        st = m.rematch(B["id"])
        self.assertEqual((st["status"], st["round"], st["turn"], st["board"]), ("playing", 2, "X", [""] * 9))
        self.assertEqual(st["players"]["X"]["seat"], 2)
        self.assertEqual(st["scores"], {"1": 1, "2": 0})
        m.play(B["id"], 0)

    def test_rematch_rejected_mid_game(self):
        m, _ = started()
        with self.assertRaises(GameError): m.rematch(A["id"])

    def test_leave_while_playing_forfeits(self):
        m, repo = started()
        st = m.leave(A["id"])
        self.assertEqual((st["status"], st["winner"], st["result"], st["opponent_left"]), ("finished", "O", "forfeit", True))
        self.assertEqual(repo.matches[0][2], B["id"])
        with self.assertRaises(GameError): m.rematch(B["id"])
        self.assertIsNone(m.leave(B["id"]))
        self.assertEqual(m.rooms, {})

    def test_leave_waiting_room_deletes_it(self):
        m = GameManager(FakeRepo())
        m.create_room(A)
        self.assertIsNone(m.leave(A["id"]))
        self.assertEqual((m.rooms, m.by_guest), ({}, {}))

    def test_quick_match_pairs_two_players(self):
        m = GameManager(FakeRepo())
        s1, _ = m.quick_match(A)
        s2, seat = m.quick_match(B)
        self.assertEqual((s1["code"], s2["status"], seat), (s2["code"], "playing", 2))
        s3, seat3 = m.quick_match(C)
        self.assertEqual((s3["status"], seat3), ("waiting", 1))

    def test_db_failure_does_not_break_game(self):
        m, repo = started()
        repo.fail = True
        with self.assertLogs("game_manager", level="ERROR"):
            st = play(m, WIN_X)
        self.assertEqual(st["status"], "finished")

    def test_room_cap(self):
        m = GameManager(FakeRepo(), max_rooms=1)
        m.create_room(A)
        with self.assertRaises(GameError): m.create_room(B)
