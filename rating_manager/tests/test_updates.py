"""updates.py のテスト"""
import unittest

from updates import latest_updates, stamp_dates


class TestStampDates(unittest.TestCase):
    def test_new_record(self):
        rec = stamp_dates({"score": 1005000, "star": 0}, {}, "2026-11-11")
        self.assertEqual(rec["date"], "2026-11-11")
        self.assertNotIn("star_date", rec)

    def test_unchanged_keeps_old_dates(self):
        old = {"score": 1005000, "star": 3, "fb": True, "date": "2026-11-11", "star_date": "2026-11-10"}
        rec = stamp_dates({"score": 1005000, "star": 3, "fb": True}, old, "2026-11-13")
        self.assertEqual(rec["date"], "2026-11-11")
        self.assertEqual(rec["star_date"], "2026-11-10")

    def test_lamp_and_star_changes(self):
        old = {"score": 1005000, "star": 3, "date": "2026-11-11"}
        rec = stamp_dates({"score": 1005000, "star": 3, "fb": True}, old, "2026-11-13")
        self.assertEqual(rec["date"], "2026-11-13")
        rec = stamp_dates({"score": 1005000, "star": 4}, old, "2026-11-13")
        self.assertEqual(rec["date"], "2026-11-11")
        self.assertEqual(rec["star_date"], "2026-11-13")


class TestLatestUpdates(unittest.TestCase):
    def setUp(self):
        self.records = {
            "a": {"date": "2026-11-11"},
            "b": {"date": "2026-11-13"},
            "c": {"date": "2026-11-13", "star_date": "2026-11-01"},
            "d": {},
            "out": {"date": "2026-11-20"},  # 枠外の更新は NEW に関係しない
        }

    def test_only_last_day(self):
        frames = {"best": [("a", 1), ("b", 1), ("d", 1)], "new": [("c", 1)], "plat": [("c", 1)]}
        self.assertEqual(latest_updates(frames, self.records), {"best": {"b"}, "new": {"c"}, "plat": set()})

    def test_mark_stays_until_next_update(self):
        frames = {"best": [("a", 1), ("d", 1)], "new": [], "plat": [("c", 1)]}
        self.assertEqual(latest_updates(frames, self.records), {"best": {"a"}, "new": set(), "plat": set()})

    def test_no_dates(self):
        frames = {"best": [("d", 1)], "new": [], "plat": []}
        self.assertEqual(latest_updates(frames, self.records), {"best": set(), "new": set(), "plat": set()})
