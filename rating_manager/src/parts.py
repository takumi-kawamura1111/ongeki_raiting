"""複数の画面で使う表示部品（難易度・ランク・ランプの色、ジャケットのスコア帯など）"""
from dom import el
from rating import BEST_FRAME_SIZE, NEW_FRAME_SIZE, PLAT_FRAME_SIZE

JACKET_URL = "https://reiwa.f5.si/jackets/ongeki/{}.webp"

DIFFS = ["BAS", "ADV", "EXP", "MAS", "LUN"]
DIFF_STYLE = {
    "BAS": ("ring-emerald-400", "bg-emerald-500"),
    "ADV": ("ring-amber-400", "bg-amber-500"),
    "EXP": ("ring-red-500", "bg-red-500"),
    "MAS": ("ring-fuchsia-500", "bg-fuchsia-600"),
    "LUN": ("ring-slate-100", "bg-slate-200 text-slate-900"),
}
RANK_COLOR = {
    "SSS+": "text-amber-300",
    "SSS": "text-pink-400",
    "SS": "text-purple-400",
    "S": "text-cyan-400",
    "AAA": "text-emerald-400",
    "-": "text-slate-500",
}
FRAME_META = {
    "best": ("ベスト枠", BEST_FRAME_SIZE),
    "new": ("新曲枠", NEW_FRAME_SIZE),
    "plat": ("P枠", PLAT_FRAME_SIZE),
}
# 理論値は AB かつ FB でしか出ないので、理論値ボタンはランプも ABFB にする
THEORETICAL_SCORE = 1010000
THEORETICAL_LAMP = "abfb"
# id -> (表示名, 色, 記録に立てるフラグ)
LAMPS = {
    "none": ("なし", "text-slate-300", ()),
    "abfb": ("ABFB", "text-pink-300", ("ab", "fb")),
    "fcfb": ("FCFB", "text-cyan-300", ("fc", "fb")),
    "fb": ("FB", "text-amber-300", ("fb",)),
    "ab": ("AB", "text-pink-400", ("ab",)),
    "fc": ("FC", "text-cyan-400", ("fc",)),
}
# ABFB・FCFB は筐体のランプの色（黄金に緑文字・黄に暗い黄文字）に合わせる
LAMP_BADGE = {
    "abfb": "bg-gradient-to-b from-[#fff6a8] to-[#e0b43a] text-[#2e7d32]",
    "ab": "bg-gradient-to-r from-pink-500 to-orange-400 text-white",
    "fcfb": "bg-[#facc15] text-[#5c3a0a]",
    "fc": "bg-cyan-500 text-white",
    "fb": "bg-amber-500 text-white",
}

# 「1,008,119 SSS+」の幅は約9.4em（字間を詰めた等幅9文字＋ランク4文字＋余白）
SCORE_BAR_EM = 9.6
SCORE_GROW_MAX = 1.4  # スコアの文字をクリアランクより大きくする上限


def jacket_url(c) -> str:
    """手動追加の曲は保存した画像（なければ空＝非表示）、公式の曲は配信元の画像"""
    if c.get("custom"):
        return c["img_data"]
    return JACKET_URL.format(c["img"])


def lamp_of(rec):
    combo = "ab" if rec.get("ab") else "fc" if rec.get("fc") else ""
    return combo + ("fb" if rec.get("fb") else "") or "none"


def render_lamps(container, selected):
    """ランプの6択ボタン。入力画面と計算タブで共通"""
    btns = []
    for lamp_id, (label, color, _) in LAMPS.items():
        active = (f"bg-slate-800 border-current {color}" if lamp_id == selected
                  else "bg-slate-900/60 border-slate-800 text-slate-500")
        btns.append(f'<button class="py-2 rounded-lg border text-[11px] font-bold leading-tight {active}" data-lamp="{lamp_id}">'
                    f'{label}</button>')
    el(container).innerHTML = "".join(btns)


# ---------- ジャケット上の表示 ----------

def lamp_fs(bar_fs):
    """ランプ札の文字サイズ（表示モード・定数表で共通、スコア帯に比例）"""
    return max(6.0, bar_fs * 0.9)


def lamp_badge(rec, fs):
    """ランプの札。jacket_bottom の右側（クリアランクのすぐ上）に置く"""
    lamp = lamp_of(rec)
    if lamp == "none":
        return ""
    return (f'<span class="font-black leading-none px-[0.3em] py-[0.15em] rounded-l-sm '
            f'{LAMP_BADGE[lamp]}" style="font-size:{fs:.1f}px">{LAMPS[lamp][0]}</span>')


def score_text(score):
    return f'<span class="bar-score font-mono tracking-[-0.04em] text-slate-100">{score:,}</span>'


def score_bar(main, rank, fs):
    """ジャケット下部の黒帯：スコア（またはP枠の★）を左、クリアランクを右に寄せる"""
    rank_html = f'<span class="bar-rank font-black tracking-[-0.03em] {RANK_COLOR[rank]}">{rank}</span>' if rank else ""
    return (f'<div class="score-bar bg-black flex items-baseline justify-between '
            f'gap-[0.3em] px-[0.2em] leading-tight font-bold whitespace-nowrap" style="font-size:{fs:.1f}px">'
            f'<span>{main}</span>{rank_html}</div>')


def jacket_bottom(left, right, bar):
    """ジャケット下端に黒帯を置き、そのすぐ上の左右に札（★・ランプ）を載せる"""
    # 札が黒帯と接して見えないよう少し浮かせる
    above = f'<div class="flex justify-between items-end mb-0.5">{left or "<span></span>"}{right}</div>' if left or right else ""
    return f'<div class="absolute bottom-0 inset-x-0 flex flex-col">{above}{bar}</div>'


def fit_score_bars(grid):
    """
    スコア帯の文字を実測して整える。
    1. 端末のフォントによってははみ出すため、収まるまで帯ごと縮める
    2. スコアの文字を、最も幅を取るカードでもクリアランクとぎりぎり重ならない大きさまで全カード揃えて広げる
    """
    bars = list(grid.querySelectorAll(".score-bar"))
    # 測定と書き換えを交互にするとレイアウト計算が毎回走るため、先に全部測る
    over = [(bar, bar.clientWidth / bar.scrollWidth) for bar in bars if bar.scrollWidth > bar.clientWidth]
    for bar, ratio in over:
        bar.style.fontSize = f"{float(bar.style.fontSize[:-2]) * ratio * 0.97:.2f}px"

    ratios = []
    scores = []
    for bar in bars:
        score, rank = bar.querySelector(".bar-score"), bar.querySelector(".bar-rank")
        if score is None or rank is None or not score.offsetWidth:
            continue
        fs = float(bar.style.fontSize[:-2])
        # 左右の余白 0.2em ずつと、ランクとの最低限の隙間 0.15em を残す
        free = bar.clientWidth - rank.offsetWidth - fs * 0.55
        # 定数表は続きを描くたびに測り直すため、すでに広げた分を除いた元の幅で比べる
        current = float(score.style.fontSize[:-2]) if score.style.fontSize else 1.0
        ratios.append(free / (score.offsetWidth / current))
        scores.append(score)
    if not ratios:
        return
    grow = min(max(min(ratios) * 0.98, 1.0), SCORE_GROW_MAX)
    for score in scores:
        score.style.fontSize = f"{grow:.3f}em"
