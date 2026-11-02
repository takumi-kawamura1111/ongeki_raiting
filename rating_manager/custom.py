"""手動で追加した曲（定数表にまだ載っていない曲）の扱い（DOM非依存）

曲の形式: {"id": "c...", "title", "artist", "version", "diffs": {"MAS": 14.5, ...}, "img": jpegのdata URL or ""}
"""
import unicodedata

DIFF_ORDER = ("BAS", "ADV", "EXP", "MAS", "LUN")


def normalize_title(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip().lower()


def song_charts(song: dict) -> dict:
    """手動追加の曲 -> {key: 譜面}。公式データの譜面と同じ項目を持たせ、custom=True で区別する"""
    out = {}
    for diff in DIFF_ORDER:
        if diff not in song["diffs"]:
            continue
        const = song["diffs"][diff]
        key = f"{song['id']}:{diff}"
        out[key] = {
            "key": key, "id": song["id"], "diff": diff, "title": song["title"], "artist": song.get("artist", ""),
            "version": song["version"], "const": const, "level": const, "is_bonus": 0, "is_unknown": 0,
            "img": "", "img_data": song.get("img", ""), "custom": True,
            # 「新しい順」の並べ替え用。id は追加した時刻（ミリ秒）から作っている
            "release_unix": int(song["id"][1:]) // 1000 if song["id"][1:].isdigit() else 0,
            "search": normalize_title(f"{song['title']} {song.get('artist', '')}"),
        }
    return out


def replace_with_official(songs: list, charts: dict, records: dict):
    """
    公式データに同じ曲名・難易度の譜面が載ったら、手動追加の譜面をそれに置き換える。
    記録は公式の譜面へ移し（公式側にまだ記録がなければ）、手動追加からはその難易度を外す。
    records はその場で書き換える。戻り値: (残った曲のリスト, 置き換えた譜面数)
    """
    official = {(normalize_title(c["title"]), c["diff"]): key
                for key, c in charts.items() if not c.get("custom")}
    remaining, replaced = [], 0
    for song in songs:
        diffs = {}
        for diff, const in song["diffs"].items():
            target = official.get((normalize_title(song["title"]), diff))
            if target is None:
                diffs[diff] = const
                continue
            rec = records.pop(f"{song['id']}:{diff}", None)
            if rec is not None and target not in records:
                records[target] = rec
            replaced += 1
        if diffs:
            remaining.append({**song, "diffs": diffs})
    return remaining, replaced
