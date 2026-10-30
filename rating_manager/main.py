import html
import math
import json
import unicodedata

from pyodide.ffi import create_once_callable, create_proxy, to_js
from pyodide.http import pyfetch
from pyscript import document, when, window

import snapshot
from history import (GRANULARITIES, bucket_label, bucketize, x_ticks,
                     y_range)
from rating import (BEST_FRAME_SIZE, NEW_FRAME_SIZE, PLAT_FRAME_SIZE,
                    calc_lamp_bonus, calc_score_rating, compute_frames,
                    frame_border, get_rank,
                    parse_score, plat_rating, rating_tier, single_rating,
                    total_if)

DATA_URL = "https://reiwa.f5.si/ongeki_record.json"
JACKET_URL = "https://reiwa.f5.si/jackets/ongeki/{}.webp"
STORE_RECORDS = "ongeki_rm_records"
STORE_NEW_VERSIONS = "ongeki_rm_new_versions"
STORE_HISTORY = "ongeki_rm_history"
STORE_GRAN = "ongeki_rm_graph_gran"
STORE_LATEST_VERSION = "ongeki_rm_latest_version"
STORE_SHORT_INPUT = "ongeki_rm_short_input"

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
STAR_LABELS = ["0", "1", "2", "3", "4", "5", "虹"]
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

charts = {}        # "id:diff" -> 譜面データ
versions = []      # 古い順
records = {}       # "id:diff" -> {"score", "fb", "fc", "ab", "star"}
history = {}       # "YYYY-MM-DD" -> その日の最終的な総合レート
new_versions = set()
frames = None
state = {"frame": "best", "selected": None, "diff": "ALL", "star": 0, "lamp": "none", "calc_lamp": "none",
         "tab": "frames", "prev_tab": "frames", "short_input": True, "gran": "day", "chart_points": []}


# ---------- ユーティリティ ----------

def el(id_):
    return document.getElementById(id_)


def normalize(s: str) -> str:
    return unicodedata.normalize("NFKC", s).lower()


def version_label(v: str) -> str:
    return v or "オンゲキ"


def storage_get(key):
    try:
        return window.localStorage.getItem(key)
    except Exception:
        return None


def storage_set(key, value):
    try:
        window.localStorage.setItem(key, value)
    except Exception:
        toast("ブラウザに保存できませんでした", error=True)


def save_records():
    storage_set(STORE_RECORDS, json.dumps(records, ensure_ascii=False))


def toast(msg, error=False):
    t = el("toast")
    t.textContent = msg
    t.classList.toggle("bg-rose-500/90", error)
    t.classList.toggle("bg-cyan-500/90", not error)
    t.classList.remove("opacity-0", "translate-y-2")
    window.clearTimeout(getattr(toast, "timer", 0))
    hide = create_once_callable(lambda *_: t.classList.add("opacity-0", "translate-y-2"))
    toast.timer = window.setTimeout(hide, 1800)


def fmt(v: float) -> str:
    return f"{v:.3f}"


# ---------- データ読み込み ----------

async def load_charts():
    resp = await pyfetch(DATA_URL)
    raw = json.loads((await resp.string()).lstrip("﻿"))
    first_release = {}
    for c in raw:
        key = f"{c['id']}:{c['diff']}"
        c["key"] = key
        c["search"] = normalize(f"{c['title']} {c['artist']}")
        charts[key] = c
        v = c["version"]
        first_release[v] = min(first_release.get(v, c["release_unix"]), c["release_unix"])
    versions.extend(sorted(first_release, key=first_release.get))


def load_storage():
    try:
        records.update(json.loads(storage_get(STORE_RECORDS) or "{}"))
    except ValueError:
        pass
    saved = storage_get(STORE_NEW_VERSIONS)
    latest, known = versions[-1], storage_get(STORE_LATEST_VERSION)
    if saved is not None and (known is None or known == latest):
        new_versions.update(v for v in json.loads(saved) if v in versions)
    else:
        # 初回、またはデータに新しいバージョンが現れたら、新曲枠をそのバージョンに切り替える
        new_versions.add(latest)
        storage_set(STORE_NEW_VERSIONS, json.dumps([latest], ensure_ascii=False))
        if saved is not None:
            state["version_notice"] = latest
    storage_set(STORE_LATEST_VERSION, latest)
    try:
        history.update(json.loads(storage_get(STORE_HISTORY) or "{}"))
    except ValueError:
        pass
    # 下4桁入力は既定でオン。自分でオフにした場合だけ "0" が保存されている
    state["short_input"] = storage_get(STORE_SHORT_INPUT) != "0"
    if storage_get(STORE_GRAN) in GRANULARITIES:
        state["gran"] = storage_get(STORE_GRAN)


# ---------- 描画 ----------

def jacket_card(c, rank_no=None, value=None, sub=None, sub_class="text-slate-300"):
    ring, badge = DIFF_STYLE[c["diff"]]
    rec = records.get(c["key"], {})
    score = rec.get("score", 0)
    rank = get_rank(score) if score else ""
    unknown = '<span class="text-amber-300">?</span>' if c["is_unknown"] else ""
    rank_html = f'<span class="text-[10px] font-black {RANK_COLOR[rank]}">{rank}</span>' if rank else "<span></span>"
    value_html = f'<span class="font-mono text-xs font-bold text-white">{value}</span>' if value is not None else ""
    no_html = (f'<span class="absolute top-1 left-1 text-[10px] font-bold font-mono px-1.5 rounded bg-black/70">#{rank_no}</span>'
               if rank_no else "")
    sub_html = f'<div class="font-mono text-[10px] {sub_class}">{sub}</div>' if sub else ""
    bonus = '<div class="absolute inset-0 bg-black/50 flex items-center justify-center text-[10px] font-bold text-slate-300">対象外</div>' if c["is_bonus"] else ""
    return f"""
    <button data-key="{c['key']}" class="jacket-card relative rounded-xl overflow-hidden ring-2 {ring} bg-slate-800 text-left transition-transform">
      <img loading="lazy" src="{JACKET_URL.format(c['img'])}" alt="" class="aspect-square w-full object-cover" onerror="this.style.opacity=0">
      {bonus}
      {no_html}
      <span class="absolute top-1 right-1 text-[9px] font-black px-1 rounded {badge}">{c['diff']} {c['const']:.1f}{unknown}</span>
      <div class="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black via-black/80 to-transparent px-1.5 pt-5 pb-1">
        <div class="text-[10px] leading-tight truncate text-slate-100">{html.escape(c['title'])}</div>
        <div class="flex items-baseline justify-between">{rank_html}{value_html}</div>
        {sub_html}
      </div>
    </button>"""


def floor4(x: float) -> float:
    return math.floor(round(x, 9) * 10000) / 10000


# 各枠の値の色（Tailwind クラス, 画像用の色）
STAT_COLORS = {"best": ("text-cyan-300", "#67e8f9"), "new": ("text-pink-400", "#f472b6"),
               "plat": ("text-yellow-300", "#fde047")}


def stats_items():
    """(枠, 表示名, 色クラス, 値)。ベ枠・新曲枠は平均、P枠はレートへの寄与（合計÷50）"""
    return (("best", "ベ枠", STAT_COLORS["best"][0], frames["sums"]["best"] / BEST_FRAME_SIZE),
            ("new", "新曲枠", STAT_COLORS["new"][0], frames["sums"]["new"] / NEW_FRAME_SIZE),
            ("plat", "P枠", STAT_COLORS["plat"][0], frames["sums"]["plat"] / PLAT_FRAME_SIZE))


def stats_boxes(current=None):
    """
    ヘッダーの各枠の箱。通常画面と表示モードで共通。値は小数第4位まで（切り捨て）：
    ベ枠・新曲枠は平均、P枠はレートへの寄与（合計÷50）
    current を渡すと、その枠の箱を枠線で強調する（表示モード用）
    """
    parts = []
    for name, label, color, value in stats_items():
        size = FRAME_META[name][1]
        ring = "ring-1 ring-slate-400" if name == current else ""
        parts.append(f"""
        <div class="bg-slate-900/60 rounded-lg px-1.5 py-1 min-w-[58px] {ring}" data-frame="{name}">
          <div class="text-slate-400 whitespace-nowrap">{label} {len(frames[name])}/{size}</div>
          <div class="font-mono font-bold {color}">{floor4(value):.4f}</div>
        </div>""")
    return "".join(parts)


def render_header():
    el("total-rating").textContent = fmt(frames["total"])
    el("total-rating").setAttribute("data-tier", rating_tier(frames["total"]))
    el("total-breakdown").innerHTML = stats_boxes()


def render_frames():
    name = state["frame"]
    label, size = FRAME_META[name]
    frame = frames[name]
    avg = sum(v for _, v in frame) / len(frame) if frame else 0
    el("frame-info").innerHTML = (f"<span>{label} 平均 <b class='font-mono text-slate-200'>{fmt(avg)}</b></span>"
                                  f"<span>下限 <b class='font-mono text-slate-200'>{fmt(frame_border(frame, size))}</b></span>")
    if not frame:
        el("frame-grid").innerHTML = """
        <div class="col-span-3 glass-card rounded-2xl p-8 text-center text-sm text-slate-400">
          まだ記録がありません。<br>検索タブから曲を登録しましょう。
        </div>"""
        return
    cards = []
    for i, (key, val) in enumerate(frame, 1):
        c = charts[key]
        sub = None
        if name == "plat":
            star = records[key].get("star", 0)
            sub = "★" * min(star, 5) + (" 虹" if star == 6 else "")
        else:
            sub = f"{records[key].get('score', 0):,}"
        cards.append(jacket_card(c, rank_no=i, value=fmt(val), sub=sub))
    el("frame-grid").innerHTML = "".join(cards)


DISPLAY_GAP = 4
FRAME_ORDER = ["best", "new", "plat"]


TITLE_FS = 1.15  # 曲名の文字サイズ（fに対する倍率）
TITLE_H = TITLE_FS * 1.3 + 0.3


DISPLAY_COLS = 5
DISPLAY_SLOTS = max(BEST_FRAME_SIZE, PLAT_FRAME_SIZE)


def display_layout(width, height, gap=DISPLAY_GAP):
    """
    表示モードのレイアウト。どの枠も5列で、カードの大きさは50曲が収まるサイズに揃える
    （新曲枠など曲が少ない枠も同じ見た目にするため）。高さが足りない分はジャケットを縮める。
    戻り値: (列数, 行の高さ, 文字サイズ, ジャケット1辺)
    """
    cols = DISPLAY_COLS
    rows = -(-DISPLAY_SLOTS // cols)
    w = (width - gap * (cols - 1)) / cols
    row_h = (height - gap * (rows - 1)) / rows
    f = min(w * 0.08, row_h * 0.12, 13)
    info_min = f * 3.7  # "17.337" が収まる最小幅
    jacket = max(0, int(min(w - info_min - 2, row_h - f * TITLE_H)))
    # 縦に余裕がある場合は行を詰め、余白は上下に回す（呼び出し側で中央寄せ）
    row_h = min(row_h, (jacket + f * TITLE_H) * 1.15)
    return cols, row_h, f, jacket


LAMP_BADGE = {
    "abfb": "bg-gradient-to-r from-pink-500 to-orange-400",
    "ab": "bg-gradient-to-r from-pink-500 to-orange-400",
    "fcfb": "bg-cyan-500",
    "fc": "bg-cyan-500",
    "fb": "bg-amber-500",
}


def lamp_badge(rec, fs, pos="top-0.5 left-0.5"):
    lamp = lamp_of(rec)
    if lamp == "none":
        return ""
    return (f'<span class="absolute {pos} font-black leading-none px-[0.3em] py-[0.15em] rounded-sm text-white '
            f'{LAMP_BADGE[lamp]}" style="font-size:{fs:.1f}px">{LAMPS[lamp][0]}</span>')


def display_card(c, no, value, rec, f, jacket, plat):
    ring, badge = DIFF_STYLE[c["diff"]]
    small = f"{f * 0.7:.1f}px"
    score = rec.get("score", 0)
    if plat:
        # P枠はジャケット上に難易度と★だけを出す（ランプ・クリアランクは出さない）
        star = rec.get("star", 0)
        main = (f'<span class="text-yellow-300">{"★" * min(star, 5)}</span>'
                + ('<span class="text-white">虹</span>' if star == 6 else ""))
        rank, lamp = "", ""
    else:
        main = score_text(score)
        rank = get_rank(score) if score else ""
        lamp = lamp_badge(rec, f * 0.75, pos="top-0.5 right-0.5")
    bar_fs = min(jacket / SCORE_BAR_EM, f * 0.95)
    return f"""
    <div class="flex flex-col justify-center min-w-0">
      <div class="flex gap-0.5">
        <div class="flex-1 min-w-0 flex flex-col justify-between leading-tight py-px" style="height:{jacket}px">
          <span class="font-black font-mono text-slate-200" style="font-size:{round(f * 1.05)}px">#{no}</span>
          <span>
            <span class="block text-slate-400" style="font-size:{small}">CONST</span>
            <span class="block font-mono font-bold rounded-sm px-[0.2em] w-fit {badge}" style="font-size:{round(f)}px">{c["const"]:.1f}</span>
          </span>
          <span>
            <span class="block text-slate-400" style="font-size:{small}">{"P-RATE" if plat else "RATING"}</span>
            <span class="block font-mono font-bold text-white" style="font-size:{round(f)}px">{value}</span>
          </span>
        </div>
        <div class="relative rounded-sm overflow-hidden ring-1 {ring} bg-slate-800 shrink-0" style="width:{jacket}px;height:{jacket}px">
          <img src="{JACKET_URL.format(c['img'])}" alt="" class="w-full h-full object-cover" onerror="this.style.opacity=0">
          <span class="absolute top-0 left-0 font-black leading-none px-[0.3em] py-[0.15em] rounded-br-sm {badge}"
            style="font-size:{f * 0.75:.1f}px">{c["diff"]}</span>
          {lamp}
          {score_bar(main, rank, bar_fs)}
        </div>
      </div>
      <div class="truncate text-slate-200 leading-tight mt-px ml-auto" style="width:{jacket}px;font-size:{f * TITLE_FS:.1f}px">{html.escape(c["title"])}</div>
    </div>"""


# 「1,008,119 SSS+」の幅は約9.4em（字間を詰めた等幅9文字＋ランク4文字＋余白）
SCORE_BAR_EM = 9.6


def score_bar(main, rank, fs):
    """ジャケット下部の黒帯：スコア（またはP枠の★）を左、クリアランクを右に寄せる"""
    rank_html = f'<span class="font-black tracking-[-0.03em] {RANK_COLOR[rank]}">{rank}</span>' if rank else ""
    return (f'<div class="score-bar absolute bottom-0 inset-x-0 bg-black flex items-baseline justify-between '
            f'gap-[0.3em] px-[0.2em] leading-tight font-bold whitespace-nowrap" style="font-size:{fs:.1f}px">'
            f'<span>{main}</span>{rank_html}</div>')


def score_text(score):
    return f'<span class="font-mono tracking-[-0.04em] text-slate-100">{score:,}</span>'


def render_display():
    if el("display").classList.contains("hidden"):
        return
    name = state["frame"]
    frame = frames[name]
    el("display-rating").textContent = fmt(frames["total"])
    el("display-rating").setAttribute("data-tier", rating_tier(frames["total"]))
    # 通常画面のヘッダーと同じ値・表記。表示中の枠は枠線で示し、タップで切り替え
    # 通常画面のヘッダーと同じ箱。表示中の枠を強調し、箱のタップで切り替え
    el("display-frame").innerHTML = stats_boxes(current=name)
    grid = el("display-grid")
    if not frame:
        grid.style.gridTemplateColumns = ""
        grid.innerHTML = '<div class="text-sm text-slate-500 py-8">この枠にはまだ曲がありません</div>'
        return
    wrap = el("display-wrap")
    cols, row_h, f, jacket = display_layout(wrap.clientWidth, wrap.clientHeight)
    # 50曲埋まっている枠は上下中央、曲が少ない枠は上詰め
    wrap.style.alignItems = "center" if len(frame) >= DISPLAY_SLOTS else "flex-start"
    grid.style.gridTemplateColumns = f"repeat({cols}, minmax(0, 1fr))"
    grid.style.gridAutoRows = f"{row_h:.1f}px"
    grid.innerHTML = "".join(display_card(charts[key], i, fmt(val), records[key], f, jacket, name == "plat")
                             for i, (key, val) in enumerate(frame, 1))
    # Tailwind CDNのスタイル生成を待ってから測る
    window.setTimeout(create_once_callable(lambda *_: fit_score_bars(grid)), 80)


def fit_score_bars(grid):
    """端末のフォントによってはスコア帯がはみ出すため、実測して収まるまで縮める"""
    # 測定と書き換えを交互にするとレイアウト計算が毎回走るため、先に全部測る
    over = [(bar, bar.clientWidth / bar.scrollWidth) for bar in grid.querySelectorAll(".score-bar")
            if bar.scrollWidth > bar.clientWidth]
    for bar, ratio in over:
        bar.style.fontSize = f"{float(bar.style.fontSize[:-2]) * ratio * 0.97:.2f}px"


def parse_float(id_):
    try:
        return float(el(id_).value)
    except ValueError:
        return None


def render_search():
    q = normalize(el("search-q").value.strip())
    diff = state["diff"]
    lo, hi = parse_float("const-min"), parse_float("const-max")
    # ボーナストラックはレート対象外なので出さない
    hits = [c for c in charts.values()
            if not c["is_bonus"]
            and (diff == "ALL" or c["diff"] == diff)
            and (lo is None or c["const"] >= lo)
            and (hi is None or c["const"] <= hi)
            and (not q or q in c["search"])]

    def score_of(c):
        return records.get(c["key"], {}).get("score", 0)

    sort = el("search-sort").value
    if sort == "new":
        hits.sort(key=lambda c: (c["release_unix"], c["const"]), reverse=True)
    else:
        # 同じ定数の中ではスコアが高い順（未登録は後ろ）
        hits.sort(key=lambda c: (c["const"], score_of(c)), reverse=True)

    grid = el("search-grid")
    card_w = (grid.clientWidth - 4 * 5) / 6 if grid.clientWidth else 56
    bar_fs = card_w / SCORE_BAR_EM

    el("search-info").textContent = f"{len(hits)}件"
    cards = []
    group = None
    for c in hits:
        # 定数順のときは定数ごとに見出しを入れる（見出しは必ず行頭から）
        if sort == "const" and c["const"] != group:
            group = c["const"]
            cards.append('<div class="col-start-1 aspect-square flex items-center justify-center rounded-sm '
                         f'bg-slate-100 text-slate-900 font-black font-mono text-[15px]">{group:.1f}</div>')
        cards.append(search_card(c, records.get(c["key"], {}), diff == "ALL", bar_fs))
    grid.innerHTML = "".join(cards) or \
        '<div class="col-span-6 text-center text-sm text-slate-500 py-8">該当する譜面がありません</div>'
    window.setTimeout(create_once_callable(lambda *_: fit_score_bars(grid)), 80)


def search_card(c, rec, show_diff, bar_fs):
    """検索結果の小さいカード。定数未確定の譜面は点線枠"""
    ring, badge = DIFF_STYLE[c["diff"]]
    frame = "border-2 border-dashed border-amber-400" if c["is_unknown"] else f"ring-1 {ring}"
    score = rec.get("score", 0)
    bar = score_bar(score_text(score), get_rank(score), bar_fs) if score else ""
    lamp = lamp_badge(rec, max(6.0, bar_fs * 0.9), pos="top-0.5 right-0.5")
    diff_html = (f'<span class="absolute top-0 left-0 text-[7px] font-black px-0.5 rounded-br-sm {badge}">{c["diff"]}</span>'
                 if show_diff else "")
    return f"""<button data-key="{c['key']}" class="jacket-card min-w-0 text-left">
      <div class="relative aspect-square rounded-sm overflow-hidden bg-slate-800 {frame}">
        <img loading="lazy" src="{JACKET_URL.format(c['img'])}" alt="" class="w-full h-full object-cover" onerror="this.style.opacity=0">
        {diff_html}{lamp}{bar}
      </div>
      <div class="truncate text-[8px] leading-tight text-slate-200 mt-px">{html.escape(c['title'])}</div>
    </button>"""


def render_settings():
    items = []
    for v in reversed(versions):
        checked = "checked" if v in new_versions else ""
        items.append(f"""
        <label class="flex items-center gap-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800 text-xs cursor-pointer">
          <input type="checkbox" class="version-cb w-4 h-4 accent-cyan-400" value="{html.escape(v)}" {checked}>
          {html.escape(version_label(v))}
        </label>""")
    el("version-list").innerHTML = "".join(items)
    el("record-count").textContent = f"登録済み：{len(records)}譜面"


def recalc():
    global frames
    frames = compute_frames(charts, records, new_versions)
    record_history()
    render_header()
    render_frames()


def today_str():
    d = window.Date.new()
    return f"{d.getFullYear():04d}-{d.getMonth() + 1:02d}-{d.getDate():02d}"


def record_history():
    """今日の総合レートを履歴に残す（1日1件、その日の最後の値で上書き）"""
    if not records:
        return
    day, total = today_str(), frames["total"]
    if history.get(day) != total:
        history[day] = total
        storage_set(STORE_HISTORY, json.dumps(history))


# ---------- 入力（エディタ） ----------

def open_editor(key):
    c = charts.get(key)
    if c is None:
        return
    state["selected"] = key
    rec = records.get(key, {})
    jacket = JACKET_URL.format(c["img"])
    el("ed-jacket").src = jacket
    el("ed-jacket-bg").src = jacket
    el("ed-title").textContent = c["title"]
    el("ed-artist").textContent = c["artist"]
    _, badge = DIFF_STYLE[c["diff"]]
    frame_name = "新曲枠" if c["version"] in new_versions else "ベスト枠"
    meta = [
        f'<span class="font-black px-1.5 rounded {badge}">{c["diff"]}</span>',
        f'<span class="font-mono font-bold">定数 {c["const"]:.1f}</span>',
    ]
    if c["is_unknown"]:
        meta.append('<span class="text-amber-300">推定</span>')
    meta.append(f'<span class="text-slate-400">{html.escape(version_label(c["version"]))}</span>')
    meta.append('<span class="text-slate-400">対象外</span>' if c["is_bonus"]
                else f'<span class="text-cyan-300">{frame_name}</span>')
    el("ed-meta").innerHTML = "".join(meta)

    chips = []
    for d in DIFFS:
        other = charts.get(f"{c['id']}:{d}")
        if other is None:
            chips.append("<span></span>")
            continue
        _, b = DIFF_STYLE[d]
        active = "ring-2 ring-white" if d == c["diff"] else "opacity-60"
        done = " ✓" if other["key"] in records else ""
        chips.append(f'<button data-key="{other["key"]}" class="text-[10px] font-black py-1 rounded-md {b} {active}">'
                     f'{d}<br><span class="font-mono">{other["const"]:.1f}{done}</span></button>')
    el("ed-diffs").innerHTML = "".join(chips)

    el("ed-score").value = str(rec["score"]) if rec.get("score") else ""
    update_score_hint("ed-score")
    state["lamp"] = lamp_of(rec)
    state["star"] = rec.get("star", 0)
    el("error-msg").classList.add("hidden")
    el("editor-empty").classList.add("hidden")
    el("editor").classList.remove("hidden")
    render_lamps()
    render_stars()
    update_preview()
    show_tab("input")


def lamp_of(rec):
    combo = "ab" if rec.get("ab") else "fc" if rec.get("fc") else ""
    return combo + ("fb" if rec.get("fb") else "") or "none"


def render_lamps(container="ed-lamps", selected=None):
    """ランプの6択ボタン。入力画面と計算タブで共通"""
    selected = state["lamp"] if selected is None else selected
    btns = []
    for lamp_id, (label, color, _) in LAMPS.items():
        active = (f"bg-slate-800 border-current {color}" if lamp_id == selected
                  else "bg-slate-900/60 border-slate-800 text-slate-500")
        btns.append(f'<button class="py-2 rounded-lg border text-[11px] font-bold leading-tight {active}" data-lamp="{lamp_id}">'
                    f'{label}</button>')
    el(container).innerHTML = "".join(btns)


def render_stars():
    btns = []
    for i, label in enumerate(STAR_LABELS):
        active = ("bg-yellow-400/20 border-yellow-300 text-yellow-200" if i == state["star"]
                  else "bg-slate-900/60 border-slate-800 text-slate-400")
        if i == 6 and i == state["star"]:
            active = "bg-gradient-to-r from-pink-500/40 via-yellow-300/40 to-cyan-400/40 border-white text-white"
        btns.append(f'<button class="star-btn py-2 rounded-lg border text-xs font-bold {active}" data-star="{i}">{label}</button>')
    el("ed-stars").innerHTML = "".join(btns)


def read_editor():
    """入力値を記録dictにする。不正ならValueError"""
    score = parse_score(el("ed-score").value, state["short_input"])
    if not 0 <= score <= 1010000:
        raise ValueError("スコアは0〜1010000の間で入力してください")
    rec = {"score": score, "star": state["star"]}
    for f in LAMPS[state["lamp"]][2]:
        rec[f] = True
    return rec


def update_preview():
    key = state["selected"]
    if key is None:
        return
    c = charts[key]
    try:
        rec = read_editor()
    except ValueError:
        el("pv-single").textContent = el("pv-plat").textContent = el("pv-total").textContent = "—"
        return
    el("pv-single").textContent = fmt(single_rating(c["const"], rec))
    el("pv-plat").textContent = fmt(plat_rating(c["const"], rec["star"]))
    after = total_if(charts, records, new_versions, key, rec)
    delta = after - frames["total"]
    sign = "text-emerald-400" if delta > 0 else "text-rose-400" if delta < 0 else "text-slate-500"
    el("pv-total").innerHTML = f'{fmt(after)} <span class="text-[10px] {sign}">{delta:+.3f}</span>'


# ---------- タブ ----------

def show_tab(name):
    if name != state["tab"]:
        state["prev_tab"] = state["tab"]
    state["tab"] = name
    for page in document.querySelectorAll(".tab-page"):
        page.classList.toggle("hidden", page.id != f"tab-{name}")
    for btn in document.querySelectorAll(".nav-btn"):
        btn.classList.toggle("active", btn.getAttribute("data-tab") == name)
    if name == "search":
        render_search()
    elif name == "settings":
        render_settings()
    elif name == "calc":
        render_lamps("calc-lamps", state["calc_lamp"])
        update_calc()
    elif name == "graph":
        set_active(".gran-chip", "data-gran", state["gran"])
        render_graph()
    window.scrollTo(0, 0)


# ---------- スコアの下4桁入力 ----------

def update_score_hint(input_id):
    """下4桁入力のとき、入力欄の下に実際のスコアとランクを出す"""
    hint = el(f"{input_id}-hint")
    if not state["short_input"]:
        hint.classList.add("hidden")
        return
    try:
        score = parse_score(el(input_id).value, True)
    except ValueError:
        score = None
    if not score:
        hint.textContent = "例：8119 → 1,008,119（10000 → 1,010,000）"
        hint.className = "score-hint text-[11px] text-slate-500 mt-1 px-1"
    elif not 0 <= score <= 1010000:
        hint.textContent = "スコアは0〜1010000の間で入力してください"
        hint.className = "score-hint text-[11px] text-rose-400 mt-1 px-1"
    else:
        rank = get_rank(score)
        hint.innerHTML = f'→ <span class="text-slate-100">{score:,}</span> <span class="font-bold {RANK_COLOR[rank]}">{rank}</span>'
        hint.className = "score-hint text-[11px] text-slate-400 mt-1 px-1 font-mono"


def apply_short_input():
    for cb in document.querySelectorAll(".short-toggle"):
        cb.checked = state["short_input"]
    update_score_hint("ed-score")
    update_score_hint("calc-score")


@when("change", ".short-toggle")
def on_short_toggle(event):
    state["short_input"] = bool(event.currentTarget.checked)
    storage_set(STORE_SHORT_INPUT, "1" if state["short_input"] else "0")
    apply_short_input()
    update_preview()
    update_calc()


@when("input", ".score-input")
def on_score_input(event):
    update_score_hint(event.currentTarget.id)


@when("focus", ".score-input")
def on_score_focus(event):
    # 下4桁入力のときは、タップしてすぐ打ち直せるよう全選択する
    if state["short_input"]:
        event.currentTarget.select()


@when("click", "#ed-back")
def on_editor_back(event):
    show_tab(state["prev_tab"] if state["prev_tab"] != "input" else "frames")


# ---------- グラフタブ ----------

CHART_W, CHART_H = 360, 220
CHART_PAD = {"left": 40, "right": 14, "top": 14, "bottom": 26}
CHART_LINE = "#67e8f9"   # cyan-300（ヘッダーのベ枠の値と同じ色）
CHART_SURFACE = "#121824"


def render_graph():
    gran = state["gran"]
    points = bucketize(history, gran)
    chart, table = el("chart"), el("chart-table")
    if not points:
        el("chart-summary").textContent = ""
        chart.innerHTML = ('<div class="text-center text-sm text-slate-500 py-12">'
                           'スコアを登録すると、その日のレートが記録されていきます</div>')
        table.innerHTML = ""
        return

    left, right, top, bottom = (CHART_PAD[k] for k in ("left", "right", "top", "bottom"))
    plot_w, plot_h = CHART_W - left - right, CHART_H - top - bottom
    first, last = points[0][0], points[-1][0]
    lo, hi, step = y_range([v for _, _, v in points])

    def x_of(o):
        return left + plot_w / 2 if first == last else left + (o - first) / (last - first) * plot_w

    def y_of(v):
        return top + (hi - v) / (hi - lo) * plot_h

    parts = []
    # 横の補助線と縦軸の目盛り
    n = round((hi - lo) / step)
    decimals = 2 if step >= 0.01 else 3
    for i in range(n + 1):
        v = lo + step * i
        y = y_of(v)
        parts.append(f'<line x1="{left}" x2="{CHART_W - right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#334155" stroke-width="0.5"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 3:.1f}" text-anchor="end" font-size="9" fill="#94a3b8" '
                     f'font-family="ui-monospace,monospace">{v:.{decimals}f}</text>')
    # 横軸の目盛り
    for o in x_ticks(first, last):
        label, x = bucket_label(o, gran), x_of(o)
        half = len(label) * 2.6  # 9px の数字1文字 ≒ 5.2px
        x = min(max(x, half + 2), CHART_W - half - 2)  # 両端の目盛りが切れないよう内側に寄せる
        parts.append(f'<text x="{x:.1f}" y="{CHART_H - 8}" text-anchor="middle" font-size="9" '
                     f'fill="#94a3b8">{label}</text>')
    # 折れ線（下を薄く塗る）と点
    xy = [(x_of(o), y_of(v)) for o, _, v in points]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    if len(xy) > 1:
        area = f"{xy[0][0]:.1f},{top + plot_h} {line} {xy[-1][0]:.1f},{top + plot_h}"
        parts.append(f'<polygon points="{area}" fill="{CHART_LINE}" fill-opacity="0.08"/>')
        parts.append(f'<polyline points="{line}" fill="none" stroke="{CHART_LINE}" stroke-width="2" '
                     f'stroke-linejoin="round" stroke-linecap="round"/>')
    for x, y in xy:
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{CHART_LINE}" stroke="{CHART_SURFACE}" stroke-width="2"/>')
    parts.append(f'<line id="chart-cross" x1="0" x2="0" y1="{top}" y2="{top + plot_h}" stroke="#e2e8f0" '
                 f'stroke-width="1" stroke-dasharray="3 3" visibility="hidden"/>')
    chart.innerHTML = (f'<svg viewBox="0 0 {CHART_W} {CHART_H}" class="w-full h-auto block" role="img" '
                       f'aria-label="総合レートの推移">{"".join(parts)}</svg>'
                       '<div id="chart-tip" class="hidden absolute pointer-events-none px-2 py-1 rounded-md text-[11px] '
                       'bg-slate-900/95 border border-slate-600 text-slate-100 whitespace-nowrap"></div>')

    rows, prev = [], None
    for o, date, v in points:
        delta = "" if prev is None else f"{v - prev:+.3f}"
        state_pts = (x_of(o), y_of(v), bucket_label(o, gran), date, v, delta)
        rows.append(state_pts)
        prev = v
    state["chart_points"] = rows

    first_v, last_v = points[0][2], points[-1][2]
    if first == last:
        el("chart-summary").textContent = f"{bucket_label(first, gran)}：{fmt(last_v)}（記録が増えると線になります）"
    else:
        el("chart-summary").textContent = (f"{bucket_label(first, gran)} 〜 {bucket_label(last, gran)}："
                                           f"{fmt(first_v)} → {fmt(last_v)}（{last_v - first_v:+.3f}）")
    table.innerHTML = "".join(
        f'<tr class="border-t border-slate-800"><td class="px-3 py-1.5 font-sans text-slate-300">{label}</td>'
        f'<td class="px-3 py-1.5 text-right text-slate-100">{fmt(v)}</td>'
        f'<td class="px-3 py-1.5 text-right {"text-emerald-400" if delta.startswith("+") and delta != "+0.000" else "text-slate-400"}">'
        f'{delta or "—"}</td></tr>'
        for _, _, label, _, v, delta in reversed(rows))


@when("click", ".gran-chip")
def on_gran(event):
    state["gran"] = event.currentTarget.getAttribute("data-gran")
    storage_set(STORE_GRAN, state["gran"])
    set_active(".gran-chip", "data-gran", state["gran"])
    render_graph()


@when("pointermove", "#chart")
def on_chart_move(event):
    show_chart_tip(event)


@when("pointerdown", "#chart")
def on_chart_down(event):
    show_chart_tip(event)


def show_chart_tip(event):
    """指やマウスの位置に一番近い点の日付と値を表示する"""
    pts = state["chart_points"]
    svg = el("chart").querySelector("svg")
    if not pts or svg is None:
        return
    rect = svg.getBoundingClientRect()
    scale = rect.width / CHART_W
    px = (event.clientX - rect.left) / scale
    x, y, label, date, v, delta = min(pts, key=lambda p: abs(p[0] - px))
    cross = el("chart-cross")
    cross.setAttribute("x1", f"{x:.1f}")
    cross.setAttribute("x2", f"{x:.1f}")
    cross.setAttribute("visibility", "visible")
    tip = el("chart-tip")
    tip.innerHTML = (f'<div class="text-slate-400">{label}（{date}）</div>'
                     f'<div class="font-mono font-bold">{fmt(v)}'
                     + (f' <span class="text-slate-400 font-normal">{delta}</span>' if delta else "") + '</div>')
    tip.classList.remove("hidden")
    # 点の上に出し、端ではみ出さないよう左右をずらす
    tx = min(max(x * scale - tip.offsetWidth / 2, 0), rect.width - tip.offsetWidth)
    tip.style.left = f"{tx:.0f}px"
    tip.style.top = f"{max(y * scale - tip.offsetHeight - 10, 0):.0f}px"


@when("pointerleave", "#chart")
def on_chart_leave(event):
    if el("chart-tip"):
        el("chart-tip").classList.add("hidden")
        el("chart-cross").setAttribute("visibility", "hidden")


# ---------- 計算タブ ----------

def update_calc():
    """定数・スコア・ランプから単曲レートを計算して表示（旧 rating_calc）"""
    err = el("calc-error")
    try:
        base = float(el("calc-const").value)
        if not el("calc-score").value.strip():
            raise ValueError
        score = parse_score(el("calc-score").value, state["short_input"])
        if not 0 <= score <= 1010000:
            raise ValueError("スコアは0〜1010000の間で入力してください")
    except ValueError as e:
        msg = str(e)
        err.textContent = msg if msg.startswith("スコア") else "譜面定数とスコアを入力してください"
        err.classList.remove("hidden")
        for id_ in ("calc-rating", "calc-base", "calc-score-bonus", "calc-lamp-bonus", "calc-rank"):
            el(id_).textContent = "—"
        return
    err.classList.add("hidden")
    rec = {"score": score, **{f: True for f in LAMPS[state["calc_lamp"]][2]}}
    score_bonus = calc_score_rating(base, score) - base
    el("calc-rating").textContent = fmt(single_rating(base, rec))
    el("calc-base").textContent = f"{base:.1f}"
    el("calc-score-bonus").textContent = f"+{score_bonus:.3f}"
    el("calc-lamp-bonus").textContent = f"+{calc_lamp_bonus(rec):.3f}"
    rank = get_rank(score)
    badge = el("calc-rank")
    badge.textContent = rank if rank != "-" else "—"
    badge.className = f"px-3 py-1 text-xs font-bold rounded-full bg-slate-800 border border-slate-700 {RANK_COLOR[rank]}"


@when("input", ".calc-input")
def on_calc_input(event):
    update_calc()


@when("click", ".calc-quick")
def on_calc_quick(event):
    score = event.currentTarget.getAttribute("data-score")
    el("calc-score").value = score
    if int(score) == THEORETICAL_SCORE:
        state["calc_lamp"] = THEORETICAL_LAMP
        render_lamps("calc-lamps", state["calc_lamp"])
    update_score_hint("calc-score")
    update_calc()


@when("click", "#calc-lamps")
def on_calc_lamp(event):
    btn = event.target.closest("[data-lamp]")
    if btn:
        state["calc_lamp"] = btn.getAttribute("data-lamp")
        render_lamps("calc-lamps", state["calc_lamp"])
        update_calc()


def set_active(selector, attr, value):
    for b in document.querySelectorAll(selector):
        b.classList.toggle("active", b.getAttribute(attr) == value)


# ---------- イベント ----------

@when("click", ".nav-btn, .nav-jump")
def on_nav(event):
    show_tab(event.currentTarget.getAttribute("data-tab"))


@when("click", "#frame-grid, #search-grid, #ed-diffs")
def on_card(event):
    card = event.target.closest("[data-key]")
    if card:
        open_editor(card.getAttribute("data-key"))


@when("click", "#display-open")
def on_display_open(event):
    el("display").classList.remove("hidden")
    render_display()


@when("click", "#display-close")
def on_display_close(event):
    el("display").classList.add("hidden")


@when("click", "#display-save")
async def on_display_save(event):
    name = state["frame"]
    if not frames[name]:
        toast("この枠にはまだ曲がありません", error=True)
        return
    toast("画像を作成中…")
    plat = name == "plat"
    cards = []
    for i, (key, val) in enumerate(frames[name], 1):
        c, rec = charts[key], records[key]
        score = rec.get("score", 0)
        lamp = None if plat else lamp_of(rec)
        cards.append({
            "no": i, "title": c["title"], "diff": c["diff"], "const": c["const"], "value": fmt(val),
            "score": score, "rank": get_rank(score) if score else "",
            "lamp": None if lamp in (None, "none") else lamp,
            "lamp_label": LAMPS[lamp][0] if lamp not in (None, "none") else "",
            "stars": rec.get("star", 0) if plat else None,
            "jacket": JACKET_URL.format(c["img"]),
        })
    header = {
        "rating": fmt(frames["total"]), "tier": rating_tier(frames["total"]),
        "stats": [(label, f"{len(frames[key])}/{FRAME_META[key][1]}", f"{floor4(value):.4f}",
                   STAT_COLORS[key][1], key == name) for key, label, _, value in stats_items()],
    }
    label = FRAME_META[name][0]
    try:
        canvas = await snapshot.render(cards, header, f"{label} · {today_str()}")
        url = canvas.toDataURL("image/png")
        blob = await (await window.fetch(url)).blob()
    except Exception as e:
        toast(f"画像を作成できませんでした：{e}", error=True)
        return
    state["snap_file"] = window.File.new(to_js([blob]), f"ongeki_{name}_{today_str()}.png",
                                         to_js({"type": "image/png"}, dict_converter=window.Object.fromEntries))
    el("snap-img").src = url
    el("snap-modal").classList.remove("hidden")


@when("click", "#snap-close")
def on_snap_close(event):
    el("snap-modal").classList.add("hidden")


@when("click", "#snap-share")
def on_snap_share(event):
    file = state.get("snap_file")
    if file is None:
        return
    payload = to_js({"files": [file]}, dict_converter=window.Object.fromEntries)
    nav = window.navigator
    if hasattr(nav, "canShare") and nav.canShare(payload):
        def on_err(e):
            if getattr(e, "name", "") != "AbortError":
                toast("共有できませんでした。画像を長押しして保存してください", error=True)
        then(nav.share(payload), lambda *_: None, on_err)
        return
    a = document.createElement("a")
    a.href = el("snap-img").src
    a.download = file.name
    a.click()


@when("click", "#display-frame")
def on_display_frame(event):
    box = event.target.closest("[data-frame]")
    if box is None:
        return
    state["frame"] = box.getAttribute("data-frame")
    set_active(".frame-chip", "data-frame", state["frame"])
    render_frames()
    render_display()


@when("click", ".frame-chip")
def on_frame_chip(event):
    state["frame"] = event.currentTarget.getAttribute("data-frame")
    set_active(".frame-chip", "data-frame", state["frame"])
    render_frames()


@when("click", ".diff-chip")
def on_diff_chip(event):
    state["diff"] = event.currentTarget.getAttribute("data-diff")
    set_active(".diff-chip", "data-diff", state["diff"])
    render_search()


@when("input", "#search-q, #const-min, #const-max")
def on_search_input(event):
    render_search()


@when("change", "#search-sort")
def on_search_sort(event):
    render_search()


@when("click", ".quick-score")
def set_quick_score(event):
    score = event.currentTarget.getAttribute("data-score")
    el("ed-score").value = score
    if int(score) == THEORETICAL_SCORE:
        state["lamp"] = THEORETICAL_LAMP
        render_lamps()
    update_score_hint("ed-score")
    update_preview()


@when("click", "#ed-stars")
def on_star(event):
    btn = event.target.closest("[data-star]")
    if btn:
        state["star"] = int(btn.getAttribute("data-star"))
        render_stars()
        update_preview()


@when("click", "#ed-lamps")
def on_lamp(event):
    btn = event.target.closest("[data-lamp]")
    if btn:
        state["lamp"] = btn.getAttribute("data-lamp")
        render_lamps()
        update_preview()


@when("input", ".ed-input")
def on_editor_input(event):
    update_preview()


@when("click", "#ed-save")
def on_save(event):
    key = state["selected"]
    try:
        rec = read_editor()
    except ValueError as e:
        err = el("error-msg")
        err.textContent = str(e)
        err.classList.remove("hidden")
        return
    el("error-msg").classList.add("hidden")
    before = frames["total"]
    if rec["score"] == 0 and rec["star"] == 0 and len(rec) == 2:
        records.pop(key, None)
    else:
        records[key] = rec
    save_records()
    recalc()
    toast(f"保存しました（{frames['total'] - before:+.3f}）")
    open_editor(key)


@when("click", "#ed-delete")
def on_delete(event):
    key = state["selected"]
    if key in records and window.confirm("この譜面の記録を削除しますか？"):
        del records[key]
        save_records()
        recalc()
        toast("削除しました")
        open_editor(key)


@when("change", "#version-list")
def on_version_change(event):
    new_versions.clear()
    for cb in document.querySelectorAll(".version-cb"):
        if cb.checked:
            new_versions.add(cb.value)
    storage_set(STORE_NEW_VERSIONS, json.dumps(sorted(new_versions), ensure_ascii=False))
    recalc()


EXPORT_NAME = "ongeki_rating_records.json"


def export_text():
    return json.dumps({"records": records, "new_versions": sorted(new_versions), "history": history},
                      ensure_ascii=False, indent=1)


def then(promise, on_ok, on_err):
    """Safariはタップ処理中に同期で呼ばないと共有・クリップボードを拒否するため、awaitせずに結果を受け取る"""
    promise.then(create_once_callable(on_ok), create_once_callable(on_err))


@when("click", "#export-btn")
def on_export(event):
    data = export_text()
    nav = window.navigator
    # iOSのホーム画面アプリではダウンロードリンクが動かないため、共有シートで保存する
    file = window.File.new(to_js([data]), EXPORT_NAME,
                           to_js({"type": "application/json"}, dict_converter=window.Object.fromEntries))
    payload = to_js({"files": [file]}, dict_converter=window.Object.fromEntries)
    if hasattr(nav, "canShare") and nav.canShare(payload):
        def on_err(e):
            if getattr(e, "name", "") != "AbortError":
                toast("書き出しに失敗しました。「コピー」をお試しください", error=True)
        then(nav.share(payload), lambda *_: None, on_err)
        return
    a = document.createElement("a")
    a.href = "data:application/json;charset=utf-8," + window.encodeURIComponent(data)
    a.download = EXPORT_NAME
    a.click()


@when("click", "#copy-btn")
def on_copy(event):
    then(window.navigator.clipboard.writeText(export_text()),
         lambda *_: toast("クリップボードにコピーしました"),
         lambda *_: toast("コピーできませんでした", error=True))


@when("click", "#paste-btn")
def on_paste(event):
    then(window.navigator.clipboard.readText(),
         import_text,
         lambda *_: toast("クリップボードを読み取れませんでした", error=True))


@when("change", "#import-file")
async def on_import(event):
    file = event.target.files.item(0)
    event.target.value = ""
    if file is None:
        return
    import_text(await file.text())


def import_text(text):
    try:
        data = json.loads(text)
        imported = data["records"]
        if not isinstance(imported, dict):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        toast("データの形式が正しくありません", error=True)
        return
    if not window.confirm(f"{len(imported)}譜面の記録を読み込みます。現在の記録は上書きされます。"):
        return
    records.clear()
    records.update(imported)
    if isinstance(data.get("history"), dict):
        history.update(data["history"])
        storage_set(STORE_HISTORY, json.dumps(history))
    if data.get("new_versions"):
        new_versions.clear()
        new_versions.update(v for v in data["new_versions"] if v in versions)
        storage_set(STORE_NEW_VERSIONS, json.dumps(sorted(new_versions), ensure_ascii=False))
    save_records()
    recalc()
    render_settings()
    toast("読み込みました")


@when("click", "#clear-btn")
def on_clear(event):
    if records and window.confirm("全ての記録（レートの推移を含む）を削除します。よろしいですか？"):
        records.clear()
        history.clear()
        storage_set(STORE_HISTORY, "{}")
        save_records()
        recalc()
        render_settings()
        toast("全記録を削除しました")


# ---------- 起動 ----------

el("loader-msg").textContent = "楽曲データを取得中…"
try:
    await load_charts()
    load_storage()
    recalc()
    window.addEventListener("resize", create_proxy(lambda *_: render_display()))
    apply_short_input()
    if state.get("version_notice"):
        toast(f"新バージョン「{version_label(state['version_notice'])}」を新曲枠に設定しました")
    el("loader").classList.add("hidden")
except Exception as e:
    el("loader-msg").textContent = f"楽曲データの取得に失敗しました：{e}"
