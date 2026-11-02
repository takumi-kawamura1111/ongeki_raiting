"""custom.py のテスト（python -m unittest test_custom）"""
import unittest

from custom import replace_with_official, song_charts


def song(**kw):
    return {"id": "c1", "title": "Demonia", "artist": "", "version": "V", "diffs": {"MAS": 14.5, "EXP": 12.0},
            "img": "", **kw}


class TestSongCharts(unittest.TestCase):
    def test_keys_and_fields(self):
        got = song_charts(song())
        self.assertEqual(list(got), ["c1:EXP", "c1:MAS"])
        self.assertEqual(got["c1:MAS"]["const"], 14.5)
        self.assertTrue(got["c1:MAS"]["custom"])
        self.assertEqual(got["c1:MAS"]["is_bonus"], 0)
        self.assertEqual(song_charts(song(id="c1793557104586"))["c1793557104586:MAS"]["release_unix"], 1793557104)


class TestReplace(unittest.TestCase):
    def test_moves_record_and_drops_matched_diff(self):
        charts = {"900:MAS": {"title": "Ｄｅｍｏｎｉａ", "diff": "MAS"}}
        charts.update(song_charts(song()))
        records = {"c1:MAS": {"score": 1007000}, "c1:EXP": {"score": 1000000}}
        remaining, replaced = replace_with_official([song()], charts, records)
        self.assertEqual(replaced, 1)
        self.assertEqual(remaining[0]["diffs"], {"EXP": 12.0})
        self.assertEqual(records, {"900:MAS": {"score": 1007000}, "c1:EXP": {"score": 1000000}})

    def test_whole_song_removed_when_all_diffs_official(self):
        charts = {"900:MAS": {"title": "demonia", "diff": "MAS"}, "900:EXP": {"title": "Demonia", "diff": "EXP"}}
        remaining, replaced = replace_with_official([song()], charts, {})
        self.assertEqual((remaining, replaced), ([], 2))

    def test_official_record_kept(self):
        charts = {"900:MAS": {"title": "Demonia", "diff": "MAS"}}
        records = {"c1:MAS": {"score": 1000000}, "900:MAS": {"score": 1008000}}
        replace_with_official([song(diffs={"MAS": 14.5})], charts, records)
        self.assertEqual(records, {"900:MAS": {"score": 1008000}})

    def test_no_match(self):
        remaining, replaced = replace_with_official([song()], {"1:MAS": {"title": "Other", "diff": "MAS"}}, {})
        self.assertEqual((len(remaining), replaced), (1, 0))


if __name__ == "__main__":
    unittest.main()
