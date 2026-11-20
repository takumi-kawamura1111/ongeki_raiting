"""ongeki_net.py のテスト"""
import json
import unittest

from ongeki_net import level_label, merged_record, parse_payload, plan_import


def chart(id_, title, diff="MAS", level=14.0, genre="オンゲキ", artist="", **kw):
    return {"key": f"{id_}:{diff}", "id": id_, "title": title, "diff": diff, "level": level, "const": level,
            "genre": genre, "artist": artist, "is_bonus": 0, **kw}


def entry(t, d="MAS", l="14", g="オンゲキ", s=1007000, **kw):
    return {"t": t, "d": d, "l": l, "g": g, "s": s, "fb": 0, "fc": 0, "ab": 0, "p": None, **kw}


CHARTS = {c["key"]: c for c in (
    chart(1, "アルカテイル", level=12.7, genre="POPS＆ANIME"),
    chart(362, "Singularity", level=14.7, artist="technoplanet"),
    chart(425, "Singularity", level=14.0, genre="VARIETY", artist="ETIA.「Arcaea」"),
    chart(487, "Singularity", level=14.0, genre="VARIETY", artist="SEGA SOUND STAFF「セガNET麻雀 MJ」"),
    chart("c1", "うたかたのせかいで", level=14.6, genre=None, custom=True),
)}


class TestParse(unittest.TestCase):
    def test_payload(self):
        self.assertEqual(parse_payload(json.dumps({"ongeki_net": 1, "songs": [entry("a")]}))[0]["t"], "a")
        self.assertIsNone(parse_payload('{"records": {}}'))
        self.assertIsNone(parse_payload("not json"))

    def test_level_label(self):
        self.assertEqual(level_label(14.7), "14+")
        self.assertEqual(level_label(14.0), "14")
        self.assertEqual(level_label(13.5), "13+")


class TestMerge(unittest.TestCase):
    def test_only_improves(self):
        old = {"score": 1009000, "fb": True, "ab": True, "star": 4, "date": "2026-01-01"}
        rec = merged_record(old, entry("x", s=1008000, fc=1, p=[960, 1000]))
        self.assertEqual((rec["score"], rec["fb"], rec["fc"], rec["ab"], rec["star"]), (1009000, True, True, True, 4))

    def test_star_from_platinum(self):
        self.assertEqual(merged_record({}, entry("x", p=[1745, 1802]))["star"], 3)
        self.assertEqual(merged_record({}, entry("x", p=[2544, 2718]))["star"], 0)
        self.assertEqual(merged_record({}, entry("x", p=[990, 1000]))["star"], 6)


class TestPlan(unittest.TestCase):
    def test_match_and_dates(self):
        records = {"1:MAS": {"score": 1009000, "fb": True, "date": "2026-01-01"}}
        ups, missing = plan_import([entry("アルカテイル", l="12+", g="POPS＆ANIME", s=1009578, fb=1, ab=1),
                                    entry("無い曲")], CHARTS, records, "2026-11-19")
        self.assertEqual(ups["1:MAS"]["score"], 1009578)
        self.assertTrue(ups["1:MAS"]["ab"])
        self.assertEqual(ups["1:MAS"]["date"], "2026-11-19")
        self.assertEqual([m["t"] for m in missing], ["無い曲"])
        self.assertNotIn("ab", records["1:MAS"])  # 元の records は書き換えない

    def test_unchanged_is_skipped(self):
        records = {"1:MAS": {"score": 1009000, "fb": True}}
        ups, _ = plan_import([entry("アルカテイル", l="12+", s=1008000, fb=1)], CHARTS, records, "2026-11-19")
        self.assertEqual(ups, {})

    def test_same_title(self):
        hint = "Singularity SEGA SOUND STAFF「セガNET麻雀 MJ」 VARIETY"
        ups, missing = plan_import([entry("Singularity", l="14+"),
                                    entry("Singularity", g="VARIETY", h=hint),
                                    entry("Singularity", g="VARIETY")], CHARTS, {}, "d")
        self.assertEqual(sorted(ups), ["362:MAS", "487:MAS"])
        self.assertEqual(len(missing), 1)  # 詳細ページが無いと ETIA 版と区別できない

    def test_custom_song_level_mismatch(self):
        # 手動追加の曲は定数をレベルとして持つため、レベル表記が合わなくても曲名で決める
        ups, missing = plan_import([entry("うたかたのせかいで", g="オンゲキ")], CHARTS, {}, "d")
        self.assertEqual(list(ups), ["c1:MAS"])

    def test_custom_preferred_over_unconfirmed_official(self):
        # 公式に載ったが定数未確定の間は、手動で追加した譜面の方に記録を入れる
        charts = {**CHARTS, "1300:MAS": chart(1300, "うたかたのせかいで", level=14.0, is_unknown=1)}
        ups, _ = plan_import([entry("うたかたのせかいで", g="オンゲキ")], charts, {}, "d")
        self.assertEqual(list(ups), ["c1:MAS"])
