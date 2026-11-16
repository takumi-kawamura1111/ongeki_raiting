"""記録を更新した日の管理と、枠のジャケットに出す NEW 表示の判定（DOM非依存）

記録には更新した日を残す:
  "date":      スコアかランプを変えた日（ベスト枠・新曲枠の値が変わる）
  "star_date": ★を変えた日（P枠の値が変わる）
"""

# 枠ごとに、値を左右する更新日
FRAME_DATE_FIELD = {"best": "date", "new": "date", "plat": "star_date"}


def stamp_dates(rec: dict, old: dict, today: str) -> dict:
    """保存する記録 rec に更新日を付ける。変わっていない項目は前の更新日を引き継ぐ"""
    score_changed = (rec.get("score", 0) != old.get("score", 0)
                     or any(bool(rec.get(f)) != bool(old.get(f)) for f in ("fb", "fc", "ab")))
    star_changed = rec.get("star", 0) != old.get("star", 0)
    for field, changed in (("date", score_changed), ("star_date", star_changed)):
        if changed:
            rec[field] = today
        elif old.get(field):
            rec[field] = old[field]
    return rec


def latest_updates(frames: dict, records: dict) -> dict:
    """
    NEW を付ける曲。枠に入っている曲のうち、最後に更新した日（全枠を通して）に更新した曲だけ。
    別の日に枠の曲を更新すると、それより前の NEW は消える。
    戻り値: {"best": {key}, "new": {key}, "plat": {key}}
    """
    dates = {name: {key: records[key].get(field) for key, _ in frames[name]}
             for name, field in FRAME_DATE_FIELD.items()}
    last = max((d for ds in dates.values() for d in ds.values() if d), default=None)
    return {name: {key for key, d in ds.items() if last and d == last} for name, ds in dates.items()}
