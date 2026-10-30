"""レーティング計算ロジック（DOM非依存）"""
import math

NEW_FRAME_SIZE = 10
BEST_FRAME_SIZE = 50
PLAT_FRAME_SIZE = 50
RATING_DIVISOR = 50

FB_BONUS = 0.050
FC_BONUS = 0.100
AB_BONUS = 0.300  # ABはFCを含むため、FC分は加算しない


def floor3(x: float) -> float:
    """小数点第3位以下切り捨て"""
    return math.floor(round(x, 9) * 1000) / 1000.0


def calc_score_rating(base: float, score: int) -> float:
    """スコア基準のレーティング計算"""
    s = score
    if 970000 <= s < 990000:
        return base + ((s - 970000) / 26.6) * 0.001
    elif s == 990000:
        return base + 0.750 + 0.100
    elif 990000 < s < 1000000:
        return base + ((s - 990000) / 20) * 0.001 + 0.100 + 0.750
    elif s == 1000000:
        return base + 1.250 + 0.200
    elif 1000000 < s < 1007500:
        return base + ((s - 1000000) / 15) * 0.001 + 0.200 + 1.250
    elif s == 1007500:
        return base + 1.750 + 0.300
    elif 1007500 < s < 1010000:
        return base + ((s - 1007500) / 10) * 0.001 + 0.300 + 1.750
    elif s >= 1010000:
        return base + 2.000 + 0.350
    else:
        return base


def calc_lamp_bonus(rec: dict) -> float:
    combo = AB_BONUS if rec.get("ab") else FC_BONUS if rec.get("fc") else 0.0
    return combo + (FB_BONUS if rec.get("fb") else 0.0)


def single_rating(const: float, rec: dict) -> float:
    """ベスト枠・新曲枠の単曲値"""
    if not rec.get("score"):
        return 0.0
    return floor3(calc_score_rating(const, rec["score"]) + calc_lamp_bonus(rec))


def plat_rating(const: float, star: int) -> float:
    """P枠の単曲値：★数 × 定数² ÷ 1000（虹★=6 は ★5 扱い）"""
    star = min(max(star or 0, 0), 5)
    return floor3(star * const * const / 1000)


def star_from_ratio(ratio: float) -> int:
    """Pスコア ÷ 最大Pスコア の割合から★数（0〜5、99%以上は虹=6）"""
    if ratio >= 0.99:
        return 6
    for star, border in ((5, 0.98), (4, 0.97), (3, 0.96), (2, 0.95), (1, 0.94)):
        if ratio >= border:
            return star
    return 0


# (下限, 色区分)。オンゲキ Re:Fresh 以降の筐体のレーティング文字色
RATING_TIERS = (
    (22.0, "rainbow-shin"),    # 虹(極)・真
    (21.0, "rainbow-kiwami"),  # 虹(極)
    (19.0, "rainbow"),         # 虹（20.000〜の光るエフェクトも同じ色で表示）
    (18.0, "platinum"),
    (17.0, "gold"),
    (15.0, "silver"),
    (13.0, "bronze"),
    (11.0, "purple"),
    (9.0, "red"),
    (7.0, "orange"),
    (4.0, "green"),
)


def rating_tier(rating: float) -> str:
    return next((tier for border, tier in RATING_TIERS if rating >= border), "aqua")


SHORT_INPUT_MAX = 10000  # 下4桁入力で 1,000,000 を足す上限（10000 → 1,010,000）


def parse_score(text: str, short: bool) -> int:
    """
    スコア入力欄の文字列をスコアにする。空欄は0、数字でなければ ValueError。
    short（下4桁入力）のときは 10000 以下を 1,000,000 + 入力値 とみなす。
    """
    text = text.strip().replace(",", "")
    if not text:
        return 0
    n = int(text)
    return 1000000 + n if short and 0 <= n <= SHORT_INPUT_MAX else n


def get_rank(score: int) -> str:
    if score >= 1007500:
        return "SSS+"
    elif score >= 1000000:
        return "SSS"
    elif score >= 990000:
        return "SS"
    elif score >= 970000:
        return "S"
    elif score >= 900000:
        return "AAA"
    return "-"


def compute_frames(charts: dict, records: dict, new_versions: set) -> dict:
    """
    charts:  key -> {"const", "version", "is_bonus", ...}
    records: key -> {"score", "fb", "fc", "ab", "star"}
    戻り値:  {"new": [(key, val)], "best": [...], "plat": [...], "sums": {...}, "total": float}
    """
    new, best, plat = [], [], []
    for key, rec in records.items():
        c = charts.get(key)
        if c is None or c["is_bonus"]:
            continue
        sv = single_rating(c["const"], rec)
        if sv > 0:
            (new if c["version"] in new_versions else best).append((key, sv))
        pv = plat_rating(c["const"], rec.get("star", 0))
        if pv > 0:
            plat.append((key, pv))

    def top(lst, n):
        return sorted(lst, key=lambda kv: kv[1], reverse=True)[:n]

    frames = {
        "new": top(new, NEW_FRAME_SIZE),
        "best": top(best, BEST_FRAME_SIZE),
        "plat": top(plat, PLAT_FRAME_SIZE),
    }
    sums = {k: sum(v for _, v in lst) for k, lst in frames.items()}
    frames["sums"] = sums
    frames["contrib"] = frame_contributions(sums)
    frames["total"] = floor3(sum(frames["contrib"].values()))
    return frames


def floor2(x: float) -> float:
    return math.floor(round(x, 9) * 100) / 100.0


def frame_contributions(sums: dict) -> dict:
    """
    各枠が総合レートに寄与する値。実機の表示値（20.869 / 20.856）と一致する端数処理：
    ベスト枠・P枠は 合計÷50 を小数第3位まで、新曲枠は 平均を小数第2位まで切り捨ててから÷5
    """
    return {
        "best": floor3(sums["best"] / RATING_DIVISOR),
        "new": floor3(floor2(sums["new"] / NEW_FRAME_SIZE) / 5),
        "plat": floor3(sums["plat"] / RATING_DIVISOR),
    }


def frame_border(frame: list, size: int) -> float:
    """枠に入るために超える必要のある値（枠が埋まっていなければ0）"""
    return frame[-1][1] if len(frame) >= size else 0.0


def total_if(charts: dict, records: dict, new_versions: set, key: str, rec: dict) -> float:
    """1譜面の記録を差し替えた場合の総合レート"""
    trial = dict(records)
    merged = dict(records.get(key, {}))
    merged.update(rec)
    trial[key] = merged
    return compute_frames(charts, trial, new_versions)["total"]
