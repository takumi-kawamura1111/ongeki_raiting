"""history.py のテスト（python -m unittest test_history）"""
import unittest

from history import bucket_label, bucket_ordinal, bucketize, nice_step, x_ticks, y_range


class TestBuckets(unittest.TestCase):
    def test_adjacent_buckets_differ_by_one(self):
        self.assertEqual(bucket_ordinal("2026-10-31", "day") + 1, bucket_ordinal("2026-11-01", "day"))
        self.assertEqual(bucket_ordinal("2026-12-01", "month") + 1, bucket_ordinal("2027-01-01", "month"))
        self.assertEqual(bucket_ordinal("2026-12-31", "year") + 1, bucket_ordinal("2027-01-01", "year"))

    def test_week_starts_monday(self):
        # 2026-10-26 は月曜、11-01 は日曜、11-02 は月曜
        self.assertEqual(bucket_ordinal("2026-10-26", "week"), bucket_ordinal("2026-11-01", "week"))
        self.assertEqual(bucket_ordinal("2026-11-01", "week") + 1, bucket_ordinal("2026-11-02", "week"))
        self.assertEqual(bucket_label(bucket_ordinal("2026-10-29", "week"), "week"), "10/26週")

    def test_labels(self):
        self.assertEqual(bucket_label(bucket_ordinal("2026-10-30", "day"), "day"), "10/30")
        self.assertEqual(bucket_label(bucket_ordinal("2026-10-30", "month"), "month"), "2026/10")
        self.assertEqual(bucket_label(bucket_ordinal("2026-10-30", "year"), "year"), "2026")

    def test_bucketize_keeps_last_value(self):
        h = {"2026-10-01": 20.1, "2026-10-20": 20.5, "2026-11-03": 20.6}
        got = bucketize(h, "month")
        self.assertEqual([(d, v) for _, d, v in got], [("2026-10-20", 20.5), ("2026-11-03", 20.6)])


class TestAxes(unittest.TestCase):
    def test_nice_step(self):
        self.assertAlmostEqual(nice_step(0.4), 0.1)
        self.assertAlmostEqual(nice_step(1.0), 0.25)

    def test_y_range_contains_values(self):
        lo, hi, step = y_range([20.869])
        self.assertLess(lo, 20.869)
        self.assertGreater(hi, 20.869)
        lo, hi, step = y_range([19.5, 20.9])
        self.assertLessEqual(lo, 19.5)
        self.assertGreaterEqual(hi, 20.9)

    def test_x_ticks_thinned(self):
        self.assertEqual(x_ticks(0, 3), [0, 1, 2, 3])
        self.assertLessEqual(len(x_ticks(0, 30)), 6)


if __name__ == "__main__":
    unittest.main()
