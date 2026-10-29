"""rating.py のテスト（python -m unittest test_rating）"""
import unittest

from rating import (compute_frames, floor3, frame_contributions, plat_rating,
                    single_rating, star_from_ratio, total_if)


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
        # 単曲 16.05、P枠 0.98 → 16.05 + 16.05/5 + 0.98
        self.assertAlmostEqual(f["total"], 16.05 + 16.05 / 5 + 0.98)

    def test_matches_in_game_rating(self):
        # (ベスト枠合計, 新曲枠合計, P枠合計) -> ゲーム内の総合レート
        for sums, expected in (((836.759, 166.265, 40.546), 20.869),
                               ((836.42, 166.265, 40.21), 20.856)):
            c = frame_contributions(dict(zip(("best", "new", "plat"), sums)))
            self.assertAlmostEqual(floor3(sum(c.values())), expected)

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



if __name__ == "__main__":
    unittest.main()
