"""表示モードの内容を画像（Canvas）に描く。

html2canvas 等の画面キャプチャは文字のグラデーション（レートの虹色）や iOS Safari で
崩れやすいため、表示モードと同じレイアウトを Canvas に直接描画する。
色は index.html / main.py の Tailwind クラスと同じ値を使っている。
"""
import asyncio

from pyscript import document, window

W = 400          # 論理幅。SCALE 倍して出力する
SCALE = 3
PAD = 10
COLS = 5
GAP = 4
HEADER_H = 64
FOOTER_H = 22

BG = "#080b11"
HEADER_BG = "#121824"
BOX_BG = "#0f172a"

# 難易度: (ジャケットの枠線, 札の背景, 札の文字)
DIFF_COLORS = {
    "BAS": ("#34d399", "#10b981", "#ffffff"),
    "ADV": ("#fbbf24", "#f59e0b", "#ffffff"),
    "EXP": ("#ef4444", "#ef4444", "#ffffff"),
    "MAS": ("#d946ef", "#c026d3", "#ffffff"),
    "LUN": ("#f1f5f9", "#e2e8f0", "#0f172a"),
}
RANK_COLORS = {"SSS+": "#fcd34d", "SSS": "#f472b6", "SS": "#c084fc", "S": "#22d3ee", "AAA": "#34d399", "-": "#64748b"}
LAMP_COLORS = {"ab": ("#ec4899", "#fb923c"), "fc": ("#06b6d4", "#06b6d4"), "fb": ("#f59e0b", "#f59e0b")}

# レートの色区分ごとのグラデーション: (向き, [(位置, 色)])。位置は数字の上端0〜下端1
TIER_GRADIENTS = {
    "aqua": ("v", [(0, "#bff4ff"), (1, "#38c8f0")]),
    "green": ("v", [(0, "#c6f8a8"), (1, "#3fc45a")]),
    "orange": ("v", [(0, "#ffe0a8"), (1, "#ff8a1f")]),
    "red": ("v", [(0, "#ffb3b3"), (1, "#f0323c")]),
    "purple": ("v", [(0, "#ecc8ff"), (1, "#a64cf0")]),
    "bronze": ("v", [(0, "#ffd9b0"), (0.55, "#c57a3e"), (1, "#8a4f22")]),
    "silver": ("v", [(0, "#ffffff"), (0.55, "#b8c2cc"), (1, "#7d8894")]),
    "gold": ("v", [(0, "#fff8c4"), (0.55, "#f2c230"), (1, "#b8860b")]),
    "platinum": ("v", [(0, "#ffffff"), (0.45, "#dfe7f5"), (0.7, "#b9c6e0"), (1, "#f3e6ff")]),
    "rainbow": ("v", [(0, "#d4ec5c"), (0.18, "#f4f09a"), (0.42, "#78d8f0"), (0.6, "#7c82f2"),
                      (0.8, "#a850e2"), (1, "#ea8ad2")]),
    "rainbow-kiwami": ("v", [(0, "#4aa8ff"), (0.18, "#9fe0ff"), (0.36, "#d8f59a"), (0.52, "#fff07a"),
                             (0.7, "#ffc0a0"), (0.88, "#ff9ac0"), (1, "#ffd08a")]),
    "rainbow-shin": ("d", [(0, "#b46cff"), (0.16, "#ff8ad6"), (0.3, "#8ff0ff"), (0.44, "#fff3a0"),
                           (0.52, "#ffffff"), (0.64, "#c78bff"), (0.78, "#ff9ad0"), (0.9, "#8fe6ff"),
                           (1, "#f4f0ff")]),
}

MONO = "ui-monospace, SFMono-Regular, Menlo, monospace"
SANS = "-apple-system, 'Hiragino Sans', 'Noto Sans JP', sans-serif"


def font(weight, size, family=SANS):
    return f"{weight} {size:.2f}px {family}"


def round_rect(ctx, x, y, w, h, r):
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.arcTo(x + w, y, x + w, y + h, r)
    ctx.arcTo(x + w, y + h, x, y + h, r)
    ctx.arcTo(x, y + h, x, y, r)
    ctx.arcTo(x, y, x + w, y, r)
    ctx.closePath()


def fit_text(ctx, text, max_w):
    """幅に収まらなければ末尾を「…」にする"""
    if ctx.measureText(text).width <= max_w:
        return text
    while text and ctx.measureText(text + "…").width > max_w:
        text = text[:-1]
    return text + "…"


def badge(ctx, x, y, text, size, bg, fg, align="left"):
    """角丸の札。align="right" のとき x は右端"""
    ctx.font = font(900, size)
    w = ctx.measureText(text).width + size * 0.6
    h = size * 1.3
    if align == "right":
        x -= w
    if isinstance(bg, tuple):
        grad = ctx.createLinearGradient(x, 0, x + w, 0)
        grad.addColorStop(0, bg[0])
        grad.addColorStop(1, bg[1])
        ctx.fillStyle = grad
    else:
        ctx.fillStyle = bg
    round_rect(ctx, x, y, w, h, size * 0.25)
    ctx.fill()
    ctx.fillStyle = fg
    ctx.textBaseline = "middle"
    ctx.fillText(text, x + size * 0.3, y + h / 2 + size * 0.05)
    ctx.textBaseline = "alphabetic"


async def load_image(url):
    img = window.Image.new()
    img.crossOrigin = "anonymous"
    # 画面表示用に CORS なしで読み込んだキャッシュを避けるため、URL を変えて取り直す
    img.src = url + "?cors=1"
    try:
        await img.decode()
        return img
    except Exception:
        return None


def draw_rating(ctx, text, tier, x, baseline, size):
    ctx.font = font(900, size, MONO)
    width = ctx.measureText(text).width
    top = baseline - size * 0.74
    kind, stops = TIER_GRADIENTS.get(tier, TIER_GRADIENTS["silver"])
    if kind == "v":
        grad = ctx.createLinearGradient(0, top, 0, baseline)
    else:
        grad = ctx.createLinearGradient(x, top, x + width, baseline)
    for pos, color in stops:
        grad.addColorStop(pos, color)
    ctx.fillStyle = grad
    ctx.fillText(text, x, baseline)


async def render(cards, header, footer):
    """
    cards:  [{"no", "title", "diff", "const", "value", "score", "rank", "lamp"(None|id), "lamp_label",
              "stars"(None|int), "jacket"}]  （stars が None でなければ P枠の表示）
    header: {"rating", "tier", "stats": [(表示名, 件数表記, 値, 色, 強調するか)]}
    footer: 画像下部の文字
    戻り値: 描画済みの canvas
    """
    rows = max(1, -(-len(cards) // COLS))
    cell_w = (W - PAD * 2 - GAP * (COLS - 1)) / COLS
    f = cell_w * 0.08
    info_w = f * 3.7
    jacket = cell_w - info_w - 2
    title_h = f * 1.8
    cell_h = jacket + title_h + 6
    height = HEADER_H + PAD + rows * cell_h + FOOTER_H

    canvas = document.createElement("canvas")
    canvas.width = int(W * SCALE)
    canvas.height = int(height * SCALE)
    ctx = canvas.getContext("2d")
    ctx.scale(SCALE, SCALE)

    images = await asyncio.gather(*(load_image(c["jacket"]) for c in cards))

    # 背景とヘッダー
    ctx.fillStyle = BG
    ctx.fillRect(0, 0, W, height)
    ctx.fillStyle = HEADER_BG
    ctx.fillRect(0, 0, W, HEADER_H)
    ctx.fillStyle = "#1e293b"
    ctx.fillRect(0, HEADER_H - 1, W, 1)

    ctx.fillStyle = "#94a3b8"
    ctx.font = font(700, 9)
    ctx.fillText("RATING", PAD + 2, 18)
    draw_rating(ctx, header["rating"], header["tier"], PAD, 50, 34)

    box_w, box_h, box_gap = 74, 36, 5
    bx = W - PAD - box_w * 3 - box_gap * 2
    for label, count, value, color, current in header["stats"]:
        round_rect(ctx, bx, 16, box_w, box_h, 6)
        ctx.fillStyle = BOX_BG
        ctx.fill()
        if current:
            ctx.strokeStyle = "#94a3b8"
            ctx.lineWidth = 1
            ctx.stroke()
        ctx.textAlign = "center"
        ctx.fillStyle = "#94a3b8"
        ctx.font = font(500, 9)
        ctx.fillText(f"{label} {count}", bx + box_w / 2, 30)
        ctx.fillStyle = color
        ctx.font = font(700, 11, MONO)
        ctx.fillText(value, bx + box_w / 2, 45)
        ctx.textAlign = "left"
        bx += box_w + box_gap

    # 曲のカード
    for i, (c, img) in enumerate(zip(cards, images)):
        x = PAD + (i % COLS) * (cell_w + GAP)
        y = HEADER_H + PAD + (i // COLS) * cell_h
        ring, badge_bg, badge_fg = DIFF_COLORS[c["diff"]]
        jx = x + cell_w - jacket

        # 左の列：順位・定数・単曲値
        ctx.fillStyle = "#e2e8f0"
        ctx.font = font(900, f * 1.05, MONO)
        ctx.fillText(f"#{c['no']}", x, y + f * 1.1)
        ctx.fillStyle = "#94a3b8"
        ctx.font = font(500, f * 0.7)
        ctx.fillText("CONST", x, y + jacket * 0.47)
        badge(ctx, x, y + jacket * 0.5, f"{c['const']:.1f}", f, badge_bg, badge_fg)
        ctx.fillStyle = "#94a3b8"
        ctx.font = font(500, f * 0.7)
        ctx.fillText("P-RATE" if c["stars"] is not None else "RATING", x, y + jacket * 0.84)
        ctx.fillStyle = "#ffffff"
        ctx.font = font(700, f, MONO)
        ctx.fillText(c["value"], x, y + jacket - 1)

        # ジャケット
        ctx.save()
        round_rect(ctx, jx, y, jacket, jacket, 2)
        ctx.clip()
        ctx.fillStyle = "#1e293b"
        ctx.fillRect(jx, y, jacket, jacket)
        if img is not None:
            ctx.drawImage(img, jx, y, jacket, jacket)

        # 左上：難易度、右上：ランプ
        badge(ctx, jx, y, c["diff"], f * 0.75, badge_bg, badge_fg)
        if c["lamp"]:
            colors = LAMP_COLORS["ab" if c["lamp"].startswith("ab") else "fc" if c["lamp"].startswith("fc") else "fb"]
            badge(ctx, jx + jacket - 1, y + 1, c["lamp_label"], f * 0.75, colors, "#ffffff", align="right")

        # 下部の黒帯：スコアとランク、P枠は★
        bar_fs = min(jacket / 9.6, f * 0.95)
        bar_h = bar_fs * 1.45
        ctx.fillStyle = "#000000"
        ctx.fillRect(jx, y + jacket - bar_h, jacket, bar_h)
        by = y + jacket - bar_h * 0.28
        ctx.textAlign = "right"
        if c["stars"] is not None:
            ctx.font = font(700, bar_fs)
            text = "★" * min(c["stars"], 5)
            if c["stars"] == 6:
                ctx.fillStyle = "#ffffff"
                ctx.fillText("虹", jx + jacket - 2, by)
                right = jx + jacket - 2 - ctx.measureText("虹 ").width
            else:
                right = jx + jacket - 2
            ctx.fillStyle = "#fde047"
            ctx.fillText(text, right, by)
        elif c["score"]:
            ctx.font = font(900, bar_fs)
            ctx.fillStyle = RANK_COLORS.get(c["rank"], "#64748b")
            ctx.fillText(c["rank"], jx + jacket - 2, by)
            rank_w = ctx.measureText(c["rank"] + " ").width
            ctx.font = font(700, bar_fs, MONO)
            ctx.fillStyle = "#f1f5f9"
            ctx.fillText(f"{c['score']:,}", jx + jacket - 2 - rank_w, by)
        ctx.textAlign = "left"
        ctx.restore()

        round_rect(ctx, jx, y, jacket, jacket, 2)
        ctx.strokeStyle = ring
        ctx.lineWidth = 0.8
        ctx.stroke()

        # 曲名
        ctx.fillStyle = "#e2e8f0"
        ctx.font = font(500, f * 1.15)
        ctx.fillText(fit_text(ctx, c["title"], jacket), jx, y + jacket + f * 1.45)

    ctx.fillStyle = "#64748b"
    ctx.font = font(500, 8)
    ctx.textAlign = "right"
    ctx.fillText(footer, W - PAD, height - 8)
    ctx.textAlign = "left"
    return canvas
