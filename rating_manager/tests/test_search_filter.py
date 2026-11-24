"""search_filter.py のテスト"""
import unittest

from search_filter import passes

C = {"version": "bright"}
ABFB = {"ab": True, "fc": True, "fb": True}
FB_ONLY = {"fb": True}
AB_ONLY = {"ab": True}


class TestFilter(unittest.TestCase):
    def test_no_filter(self):
        self.assertTrue(passes(C, {}, set(), set()))

    def test_lamps_all_must_hold(self):
        self.assertTrue(passes(C, FB_ONLY, {"fb", "no_ab"}, set()))
        self.assertFalse(passes(C, ABFB, {"fb", "no_ab"}, set()))

    def test_ab_counts_as_fc(self):
        self.assertTrue(passes(C, AB_ONLY, {"fc"}, set()))
        self.assertFalse(passes(C, AB_ONLY, {"no_fc"}, set()))

    def test_abfb(self):
        self.assertTrue(passes(C, ABFB, {"abfb"}, set()))
        self.assertTrue(passes(C, AB_ONLY, {"no_abfb"}, set()))
        self.assertTrue(passes(C, {}, {"no_abfb"}, set()))  # 未プレイは「未」に入る

    def test_versions_any(self):
        self.assertTrue(passes(C, {}, set(), {"bright", "R.E.D."}))
        self.assertFalse(passes(C, {}, set(), {"R.E.D."}))
