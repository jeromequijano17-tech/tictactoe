import unittest
from game_logic import LINES, check_winner, is_full, new_board


class LogicTests(unittest.TestCase):
    def test_all_eight_lines_win(self):
        for line in LINES:
            b = new_board()
            for i in line:
                b[i] = "X"
            self.assertEqual(check_winner(b), ("X", list(line)))

    def test_no_winner_empty_and_mixed(self):
        self.assertEqual(check_winner(new_board()), (None, None))
        b = list("XOXXOOOXX")
        self.assertEqual(check_winner(b), (None, None))
        self.assertTrue(is_full(b))

    def test_not_full(self):
        self.assertFalse(is_full(new_board()))
