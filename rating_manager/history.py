"""レート推移グラフの集計（DOM非依存）"""
import datetime as dt
import math

# 横軸の区切り。id -> 表示名
GRANULARITIES = {"day": "日", "week": "週", "month": "月", "year": "年"}


def bucket_ordinal(date_str: str, gran: str) -> int:
    """日付を区切りごとの通し番号に変換する（隣の区間とちょうど1違う）"""
    d = dt.date.fromisoformat(date_str)
    if gran == "day":
        return d.toordinal()
    if gran == "week":  # 月曜始まり。ordinal 1 (0001-01-01) は月曜
        return (d.toordinal() - 1) // 7
    if gran == "month":
        return d.year * 12 + d.month - 1
    return d.year


def bucket_label(ordinal: int, gran: str) -> str:
    if gran == "day":
        d = dt.date.fromordinal(ordinal)
        return f"{d.month}/{d.day}"
    if gran == "week":
        d = dt.date.fromordinal(ordinal * 7 + 1)
        return f"{d.month}/{d.day}週"
    if gran == "month":
        return f"{ordinal // 12}/{ordinal % 12 + 1:02d}"
    return str(ordinal)


def bucketize(history: dict, gran: str) -> list:
    """
    history: {"YYYY-MM-DD": レート}
    戻り値: 区間ごとの最後の値 [(通し番号, 最後の日付, レート)]（古い順）
    """
    last = {}
    for date in sorted(history):
        last[bucket_ordinal(date, gran)] = (date, history[date])
    return [(o, *last[o]) for o in sorted(last)]


def nice_step(span: float, target: int = 4) -> float:
    """目盛り間隔を 1, 2, 2.5, 5 ×10^n から選ぶ"""
    raw = max(span, 0.001) / target
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag + 1e-12)


def y_range(values: list) -> tuple:
    """縦軸の (下限, 上限, 目盛り間隔)。値が1つでも幅を持たせる"""
    lo, hi = min(values), max(values)
    pad = max((hi - lo) * 0.15, 0.02)
    step = nice_step(hi - lo + pad * 2)
    return math.floor((lo - pad) / step) * step, math.ceil((hi + pad) / step) * step, step


def x_ticks(first: int, last: int, max_labels: int = 6) -> list:
    """横軸に目盛りを置く通し番号。多すぎる場合は間引く"""
    every = max(1, math.ceil((last - first + 1) / max_labels))
    return list(range(first, last + 1, every))
