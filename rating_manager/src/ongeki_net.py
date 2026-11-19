"""オンゲキネットから取得した記録（ongeki_net.js が作る JSON）の取り込み（DOM非依存）

取得データの各譜面: {"t": 曲名, "d": "MAS", "l": "14+", "g": ジャンル, "s": スコア, "fb", "fc", "ab": 0/1,
                    "p": [プラチナスコア, 最大] or None, "h": 詳細ページの本文（曲名が重複する譜面のみ）}
記録は良くなる方向にだけ書き換える（スコア・★は高い方、ランプは取ったものを足す）
"""
import json

from custom import normalize_title
from rating import star_from_ratio
from updates import stamp_dates

LAMPS = ("fb", "fc", "ab")


def parse_payload(text: str):
    """オンゲキネットの取得データなら譜面のリストを返す。違う形式なら None"""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "ongeki_net" not in data or not isinstance(data.get("songs"), list):
        return None
    return data["songs"]


def level_label(level: float) -> str:
    """譜面のレベル（14.7 など）をオンゲキネットの表記（14+）にする"""
    whole = int(level)
    return f"{whole}+" if level - whole >= 0.5 else str(whole)


def find_chart(entry: dict, by_title: dict, charts: dict):
    """
    取得した譜面に当たる key。曲名と難易度で探し、候補が複数あればジャンル・レベル・
    詳細ページに書かれたアーティストで絞る（絞った結果が0件になる条件は使わない）。決まらなければ None
    """
    keys = by_title.get((normalize_title(entry.get("t", "")), entry.get("d")), [])
    hint = normalize_title(entry.get("h") or "")
    narrowers = (
        lambda c: c.get("genre") == entry.get("g"),
        lambda c: level_label(c["level"]) == entry.get("l"),
        lambda c: bool(hint) and bool(c.get("artist")) and normalize_title(c["artist"]) in hint,
    )
    for keep in narrowers:
        if len(keys) <= 1:
            break
        narrowed = [k for k in keys if keep(charts[k])]
        if narrowed:
            keys = narrowed
    return keys[0] if len(keys) == 1 else None


def merged_record(old: dict, entry: dict) -> dict:
    """今の記録 old に取得した記録を合わせたもの（悪くなる項目は今の記録のまま）"""
    rec = dict(old)
    rec["score"] = max(old.get("score", 0), int(entry.get("s") or 0))
    for lamp in LAMPS:
        rec[lamp] = bool(old.get(lamp)) or bool(entry.get(lamp))
    plat = entry.get("p")
    star = star_from_ratio(plat[0] / plat[1]) if plat and plat[1] else 0
    rec["star"] = max(old.get("star", 0), star)
    return rec


def plan_import(entries: list, charts: dict, records: dict, today: str):
    """
    取り込みで変わる記録を求める（records は書き換えない）。
    戻り値: (更新する記録 {key: rec}, 見つからなかった譜面のリスト)
    """
    by_title = {}
    for key, c in charts.items():
        if not c.get("is_bonus"):
            by_title.setdefault((normalize_title(c["title"]), c["diff"]), []).append(key)
    updates, missing = {}, []
    for entry in entries:
        key = find_chart(entry, by_title, charts)
        if key is None:
            missing.append(entry)
            continue
        old = updates.get(key) or records.get(key, {})
        rec = merged_record(old, entry)
        if any(rec.get(f, 0) != old.get(f, 0) for f in ("score", "star")) or \
                any(bool(rec[f]) != bool(old.get(f)) for f in LAMPS):
            updates[key] = stamp_dates(rec, records.get(key, {}), today)
    return updates, missing
