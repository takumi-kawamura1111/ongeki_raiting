import html
import json
import unicodedata

from pyodide.ffi import create_once_callable, create_proxy, to_js
from pyodide.http import pyfetch
from pyscript import document, when, window

from rating import (BEST_FRAME_SIZE, NEW_FRAME_SIZE, PLAT_FRAME_SIZE,
                    RATING_DIVISOR, calc_lamp_bonus, compute_frames, floor3,
                    frame_border, get_rank,
                    plat_rating, single_rating, total_if)

DATA_URL = "https://reiwa.f5.si/ongeki_record.json"
JACKET_URL = "https://reiwa.f5.si/jackets/ongeki/{}.webp"
STORE_RECORDS = "ongeki_rm_records"
STORE_NEW_VERSIONS = "ongeki_rm_new_versions"

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
new_versions = set()
frames = None
state = {"frame": "best", "selected": None, "diff": "MAS", "star": 0, "lamp": "none"}


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
    if saved is not None:
        new_versions.update(v for v in json.loads(saved) if v in versions)
    else:
        new_versions.add(versions[-1])


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


def render_header():
    el("total-rating").textContent = fmt(frames["total"])
    parts = []
    # ベスト枠・P枠はレートへの寄与（＝ベスト枠は平均）、新曲枠は寄与ではなく平均を表示
    new_avg = floor3(frames["sums"]["new"] / NEW_FRAME_SIZE)
    items = (("best", "ベ枠", "text-cyan-300", frames["contrib"]["best"]),
             ("new", "新曲枠", "text-pink-400", new_avg),
             ("plat", "P枠", "text-yellow-300", frames["contrib"]["plat"]))
    for name, label, color, value in items:
        size = FRAME_META[name][1]
        parts.append(f"""
        <div class="bg-slate-900/60 rounded-lg px-1.5 py-1 min-w-[58px]">
          <div class="text-slate-400 whitespace-nowrap">{label} {len(frames[name])}/{size}</div>
          <div class="font-mono font-bold {color}">{fmt(value)}</div>
        </div>""")
    el("total-breakdown").innerHTML = "".join(parts)


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


def display_layout(n, width, height, gap=DISPLAY_GAP):
    """
    表示モードのレイアウト。列数は曲数で固定し（10曲以下は2列、それ以上は5列）、
    高さが足りない分はジャケットを縮めて合わせる。
    戻り値: (列数, 行の高さ, 文字サイズ, ジャケット1辺)
    """
    cols = 2 if n <= 10 else 5
    rows = -(-n // cols)
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
    rank = get_rank(score) if score else ""
    if plat:
        star = rec.get("star", 0)
        main = (f'<span class="text-yellow-300">{"★" * min(star, 5)}</span>'
                + ('<span class="text-white">虹</span>' if star == 6 else ""))
    else:
        main = score_text(score)
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
          {lamp_badge(rec, f * 0.75)}
          {score_bar(main, rank, bar_fs)}
        </div>
      </div>
      <div class="truncate text-slate-200 leading-tight mt-px ml-auto" style="width:{jacket}px;font-size:{f * TITLE_FS:.1f}px">{html.escape(c["title"])}</div>
    </div>"""


# 「1,008,119 SSS+」の幅は約9.4em（字間を詰めた等幅9文字＋ランク4文字＋余白）
SCORE_BAR_EM = 9.6


def score_bar(main, rank, fs):
    """ジャケット下部の黒帯：スコア（またはP枠の★）とクリアランク"""
    rank_html = f'<span class="font-black tracking-[-0.03em] {RANK_COLOR[rank]}">{rank}</span>' if rank else ""
    return (f'<div class="score-bar absolute bottom-0 inset-x-0 bg-black flex items-baseline gap-[0.3em] px-[0.2em] '
            f'leading-tight font-bold whitespace-nowrap" style="font-size:{fs:.1f}px">'
            f'<span class="ml-auto">{main}</span>{rank_html}</div>')


def score_text(score):
    return f'<span class="font-mono tracking-[-0.04em] text-slate-100">{score:,}</span>'


def avg_of(name):
    frame = frames[name]
    return sum(v for _, v in frame) / len(frame) if frame else 0


def render_display():
    if el("display").classList.contains("hidden"):
        return
    name = state["frame"]
    label, size_max = FRAME_META[name]
    frame = frames[name]
    el("display-rating").textContent = fmt(frames["total"])
    # 色は通常画面のヘッダーと揃える
    stats = (("BEST", avg_of("best"), "text-cyan-300"), ("NEW", avg_of("new"), "text-pink-400"),
             ("P", frames["sums"]["plat"] / RATING_DIVISOR, "text-yellow-300"))
    el("display-frame").innerHTML = (
        f'<div class="text-slate-100 font-bold text-[11px] whitespace-nowrap">{label} {len(frame)}/{size_max} '
        f'<i class="fa-solid fa-rotate text-slate-500 ml-0.5"></i></div>'
        '<div class="grid grid-cols-[auto_auto] gap-x-1.5 font-mono text-[10px] leading-tight whitespace-nowrap">'
        + "".join(f'<span class="text-slate-500">{k}</span><span class="font-bold {color}">{v:.4f}</span>'
                  for k, v, color in stats)
        + '</div>')
    grid = el("display-grid")
    if not frame:
        grid.style.gridTemplateColumns = ""
        grid.innerHTML = '<div class="text-sm text-slate-500 py-8">この枠にはまだ曲がありません</div>'
        return
    wrap = el("display-wrap")
    cols, row_h, f, jacket = display_layout(len(frame), wrap.clientWidth, wrap.clientHeight)
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
    hits = [c for c in charts.values()
            if (diff == "ALL" or c["diff"] == diff)
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
    bonus = ('<div class="absolute inset-0 bg-black/60 flex items-center justify-center text-[8px] font-bold">対象外</div>'
             if c["is_bonus"] else "")
    return f"""<button data-key="{c['key']}" class="jacket-card min-w-0 text-left">
      <div class="relative aspect-square rounded-sm overflow-hidden bg-slate-800 {frame}">
        <img loading="lazy" src="{JACKET_URL.format(c['img'])}" alt="" class="w-full h-full object-cover" onerror="this.style.opacity=0">
        {bonus}{diff_html}{lamp}{bar}
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
    render_header()
    render_frames()


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


def render_lamps():
    btns = []
    for lamp_id, (label, color, flags) in LAMPS.items():
        active = (f"bg-slate-800 border-current {color}" if lamp_id == state["lamp"]
                  else "bg-slate-900/60 border-slate-800 text-slate-500")
        bonus = f'+{calc_lamp_bonus({f: True for f in flags}):.2f}'
        btns.append(f'<button class="py-1.5 rounded-lg border text-[11px] font-bold leading-tight {active}" data-lamp="{lamp_id}">'
                    f'{label}<div class="font-mono text-[9px] opacity-70">{bonus}</div></button>')
    el("ed-lamps").innerHTML = "".join(btns)


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
    s = el("ed-score").value.strip()
    score = int(s) if s else 0
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
    for page in document.querySelectorAll(".tab-page"):
        page.classList.toggle("hidden", page.id != f"tab-{name}")
    for btn in document.querySelectorAll(".nav-btn"):
        btn.classList.toggle("active", btn.getAttribute("data-tab") == name)
    if name == "search":
        render_search()
    elif name == "settings":
        render_settings()
    window.scrollTo(0, 0)


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


@when("click", "#display-frame")
def on_display_frame(event):
    state["frame"] = FRAME_ORDER[(FRAME_ORDER.index(state["frame"]) + 1) % len(FRAME_ORDER)]
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
    el("ed-score").value = event.currentTarget.getAttribute("data-score")
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
    return json.dumps({"records": records, "new_versions": sorted(new_versions)}, ensure_ascii=False, indent=1)


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
    if records and window.confirm("全ての記録を削除します。よろしいですか？"):
        records.clear()
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
    el("loader").classList.add("hidden")
except Exception as e:
    el("loader-msg").textContent = f"楽曲データの取得に失敗しました：{e}"
