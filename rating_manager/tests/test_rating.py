"""rating.py のテスト"""
import unittest

from rating import (compute_frames, floor3, frame_contributions, naive_sum, plat_rating,
                    parse_score, rating_tier, single_rating, star_from_ratio,
                    total_if)


def chart(const, version="old", is_bonus=0):
    return {"const": const, "version": version, "is_bonus": is_bonus}


class TestSingle(unittest.TestCase):
    def test_plat_examples(self):
        self.assertAlmostEqual(plat_rating(13.3, 5), 0.884)
        self.assertAlmostEqual(plat_rating(14.7, 4), 0.864)
        self.assertAlmostEqual(plat_rating(14.7, 6), plat_rating(14.7, 5))
        self.assertEqual(plat_rating(14.7, 0), 0.0)

    def test_star_borders(self):
        self.assertEqual(star_from_ratio(0.9399), 0)
        self.assertEqual(star_from_ratio(0.94), 1)
        self.assertEqual(star_from_ratio(0.98), 5)
        self.assertEqual(star_from_ratio(0.99), 6)

    def test_single_with_lamp(self):
        rec = {"score": 1010000, "fb": True, "fc": True, "ab": True}
        self.assertAlmostEqual(single_rating(14.0, rec), 14.0 + 2.35 + 0.35)
        self.assertEqual(single_rating(14.0, {}), 0.0)

    def test_reference_tool_values(self):
        # ベスト枠画像ジェネレーターの表示値と一致すること
        self.assertAlmostEqual(single_rating(14.7, {"score": 1009820, "ab": True, "fb": True}), 17.332)
        self.assertAlmostEqual(single_rating(14.9, {"score": 1004387, "fc": True, "fb": True}), 16.792)
        self.assertAlmostEqual(single_rating(14.4, {"score": 1007360, "ab": True, "fb": True}), 16.690)
        self.assertAlmostEqual(single_rating(15.1, {"score": 999306, "fb": True}), 16.465)


class TestParseScore(unittest.TestCase):
    def test_short_input(self):
        self.assertEqual(parse_score("8119", True), 1008119)
        self.assertEqual(parse_score("0", True), 1000000)
        self.assertEqual(parse_score("10000", True), 1010000)
        self.assertEqual(parse_score("999306", True), 999306)
        self.assertEqual(parse_score("1008119", True), 1008119)
        self.assertEqual(parse_score("", True), 0)

    def test_full_input(self):
        self.assertEqual(parse_score("8119", False), 8119)
        self.assertEqual(parse_score("1,008,119", False), 1008119)
        with self.assertRaises(ValueError):
            parse_score("abc", False)


class TestTier(unittest.TestCase):
    def test_borders(self):
        cases = [(0, "aqua"), (3.999, "aqua"), (4.0, "green"), (12.999, "purple"), (13.0, "bronze"),
                 (17.999, "gold"), (18.0, "platinum"), (19.0, "rainbow"), (20.869, "rainbow"),
                 (21.0, "rainbow-kiwami"), (22.5, "rainbow-shin")]
        for rating, tier in cases:
            self.assertEqual(rating_tier(rating), tier, rating)


class TestFrames(unittest.TestCase):
    def test_frame_sizes_and_total(self):
        charts, records = {}, {}
        for i in range(60):
            charts[f"o{i}"] = chart(14.0)
            records[f"o{i}"] = {"score": 1007500, "star": 5}
        for i in range(15):
            charts[f"n{i}"] = chart(14.0, "NEW")
            records[f"n{i}"] = {"score": 1007500}
        f = compute_frames(charts, records, {"NEW"})
        self.assertEqual(len(f["best"]), 50)
        self.assertEqual(len(f["new"]), 10)
        self.assertEqual(len(f["plat"]), 50)
        # 単曲 16.05、P枠 0.98 → 16.05 + 16.05/5 + 0.98。同じ値ばかりだと合計がちょうど切り捨ての
        # 境目になり、実機どおりの浮動小数点の誤差で 0.001〜0.002 下がる
        self.assertAlmostEqual(f["total"], 16.05 + 16.05 / 5 + 0.98, delta=0.003)

    def test_matches_in_game_rating(self):
        # (ベスト枠合計, 新曲枠合計, P枠合計) -> ゲーム内の総合レート
        for sums, expected in (((836.759, 166.265, 40.546), 20.869),
                               ((836.42, 166.265, 40.21), 20.856)):
            c = frame_contributions(dict(zip(("best", "new", "plat"), sums)))
            self.assertAlmostEqual(floor3(sum(c.values())), expected)

    def test_matches_in_game_on_rounding_boundary(self):
        # ベスト枠の合計がちょうど 836.900 になるケース。実機は 20.882（ベ枠 16.737）
        best = [17.337, 17.061, 16.94, 16.917, 16.882, 16.872, 16.861, 16.859, 16.849, 16.841, 16.809, 16.792,
                16.787, 16.777, 16.771, 16.77, 16.76, 16.76, 16.76, 16.755, 16.754, 16.744, 16.735, 16.731,
                16.724, 16.714, 16.693, 16.687, 16.683, 16.668, 16.665, 16.661, 16.66, 16.654, 16.654, 16.652,
                16.646, 16.641, 16.634, 16.63, 16.629, 16.626, 16.625, 16.624, 16.618, 16.613, 16.596, 16.593,
                16.593, 16.593]
        new = [17.019, 16.859, 16.784, 16.752, 16.603, 16.587, 16.577, 16.554, 16.465, 16.435]
        plat = [1.08, 0.911, 0.884, 0.884] + [0.845] * 4 + [0.832] * 9 + [0.819] * 6 + [0.806] * 7 \
            + [0.793] * 4 + [0.781] * 7 + [0.768] * 6 + [0.756] * 3
        c = frame_contributions({"best": naive_sum(best), "new": naive_sum(new), "plat": naive_sum(plat)})
        self.assertEqual(c["best"], 16.737)
        self.assertAlmostEqual(floor3(sum(c.values())), 20.882)

    def test_bonus_excluded(self):
        charts = {"b": chart(14.0, is_bonus=1)}
        f = compute_frames(charts, {"b": {"score": 1007500, "star": 5}}, set())
        self.assertEqual(f["total"], 0.0)

    def test_total_if(self):
        charts = {"a": chart(14.0)}
        records = {"a": {"score": 1000000}}
        before = compute_frames(charts, records, set())["total"]
        after = total_if(charts, records, set(), "a", {"score": 1007500})
        self.assertGreater(after, before)
        self.assertEqual(records["a"]["score"], 1000000)

    def test_total_if_lamp_downgrade(self):
        # ABFB → FCFB に変えたら、元の AB が残らずレートが下がること
        charts = {"a": chart(14.0)}
        records = {"a": {"score": 1007500, "ab": True, "fb": True}}
        before = compute_frames(charts, records, set())["total"]
        after = total_if(charts, records, set(), "a", {"score": 1007500, "fc": True, "fb": True})
        self.assertLess(after, before)



if __name__ == "__main__":
    unittest.main()
