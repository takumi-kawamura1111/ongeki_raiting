"""上部のレート表示、枠タブ、表示モード（全画面）と、その画像保存"""
import html
import math

from pyodide.ffi import create_once_callable, create_proxy, to_js
from pyscript import when, window

import snapshot
from dom import el, fmt, js_obj, share_or_download, today_str, toast
from parts import (DIFF_STYLE, FRAME_META, SCORE_BAR_EM, fit_score_bars, jacket_bottom, jacket_url, lamp_badge,
                   lamp_fs, lamp_medals, score_bar, score_text)
from rating import BEST_FRAME_SIZE, NEW_FRAME_SIZE, PLAT_FRAME_SIZE, get_rank, rating_tier
from store import charts, frames, recompute, records, state
from tabs import on_show, show_tab

DISPLAY_GAP = 4
DISPLAY_COLS = 5
DISPLAY_SLOTS = max(BEST_FRAME_SIZE, PLAT_FRAME_SIZE)
TITLE_FS = 1.15  # 曲名の文字サイズ（fに対する倍率）
TITLE_H = TITLE_FS * 1.3 + 0.3


def recalc():
    """記録が変わったときに呼ぶ。レートを計算し直し、上部と枠タブを描き直す"""
    recompute()
    render_header()
    render_frames()


# ---------- 上部のレート ----------

def floor4(x: float) -> float:
    return math.floor(round(x, 9) * 10000) / 10000


def stats_items():
    """(枠, 表示名, 値)。ベ枠・新曲枠は平均、P枠はレートへの寄与（合計÷50）"""
    return (("best", "ベ枠", frames["sums"]["best"] / BEST_FRAME_SIZE),
            ("new", "新曲枠", frames["sums"]["new"] / NEW_FRAME_SIZE),
            ("plat", "P枠", frames["sums"]["plat"] / PLAT_FRAME_SIZE))


def stats_boxes(current=None):
    """
    ヘッダーの各枠の箱。通常画面と表示モードで共通。値は小数第4位まで（切り捨て）：
    ベ枠・新曲枠は平均、P枠はレートへの寄与（合計÷50）
    current を渡すと、その枠の箱を枠線で強調する
    """
    parts = []
    for name, label, value in stats_items():
        size = FRAME_META[name][1]
        ring = "ring-1 ring-slate-400" if name == current else ""
        # 値は白で、見出しより一回り大きく太くして目立たせる
        parts.append(f"""
        <div class="bg-slate-900/60 rounded-lg px-1.5 py-1 min-w-[58px] {ring}" data-frame="{name}">
          <div class="text-slate-400 whitespace-nowrap">{label} {len(frames[name])}/{size}</div>
          <div class="font-mono font-extrabold text-white text-[12px] leading-snug">{floor4(value):.4f}</div>
        </div>""")
    return "".join(parts)


def render_header():
    el("total-rating").textContent = fmt(frames["total"])
    el("total-rating").setAttribute("data-tier", rating_tier(frames["total"]))
    # 表示中の枠を強調し、箱のタップで枠を切り替える（表示モードと同じ）
    el("total-breakdown").innerHTML = stats_boxes(current=state["frame"])


@when("click", "#total-breakdown")
def on_header_frame(event):
    box = event.target.closest("[data-frame]")
    if box is None:
        return
    state["frame"] = box.getAttribute("data-frame")
    render_header()
    # 他のタブから押したときは枠タブに移る（show_tab が枠を描き直す）
    if state["tab"] == "frames":
        render_frames()
    else:
        show_tab("frames")


# ---------- 枠のカード（枠タブと表示モードで共通） ----------

def display_layout(width, height, gap=DISPLAY_GAP):
    """
    枠のカードのレイアウト。どの枠も5列で、カードの大きさは50曲が収まるサイズに揃える
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


def display_card(c, no, value, rec, f, jacket, plat):
    ring, badge = DIFF_STYLE[c["diff"]]
    small = f"{f * 0.7:.1f}px"
    score = rec.get("score", 0)
    bar_fs = min(jacket / SCORE_BAR_EM, f * 1.2)
    if plat:
        # P枠はジャケット上に難易度と★だけを出す（ランプ・クリアランクは出さない）
        star = rec.get("star", 0)
        main = (f'<span class="text-yellow-300">{"★" * min(star, 5)}</span>'
                + ('<span class="text-white">虹</span>' if star == 6 else ""))
        rank, lamp = "", ""
    else:
        main = score_text(score)
        rank = get_rank(score) if score else ""
        lamp = lamp_badge(rec, lamp_fs(bar_fs))
    return f"""
    <div data-key="{c['key']}" class="jacket-card flex flex-col justify-center min-w-0 cursor-pointer">
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
          <img src="{jacket_url(c)}" alt="" class="w-full h-full object-cover" onerror="this.style.opacity=0">
          <span class="absolute top-0 left-0 font-black leading-none px-[0.3em] py-[0.15em] rounded-br-sm {badge}"
            style="font-size:{f * 0.75:.1f}px">{c["diff"]}</span>
          {jacket_bottom("", lamp, score_bar(main, rank, bar_fs))}
        </div>
      </div>
      <div class="truncate text-slate-200 leading-tight mt-px ml-auto" style="width:{jacket}px;font-size:{f * TITLE_FS:.1f}px">{html.escape(c["title"])}</div>
    </div>"""


def fill_grid(grid, width, height):
    """grid に今の枠のカードを並べる。戻り値は並べた曲数"""
    name = state["frame"]
    frame = frames[name]
    cols, row_h, f, jacket = display_layout(width, height)
    grid.style.gridTemplateColumns = f"repeat({cols}, minmax(0, 1fr))"
    grid.style.gridAutoRows = f"{row_h:.1f}px"
    grid.innerHTML = "".join(display_card(charts[key], i, fmt(val), records[key], f, jacket, name == "plat")
                             for i, (key, val) in enumerate(frame, 1))
    # Tailwind CDNのスタイル生成を待ってから測る
    window.setTimeout(create_once_callable(lambda *_: fit_score_bars(grid)), 80)


# ---------- 枠タブ ----------

@on_show("frames")
def render_frames():
    grid = el("frame-grid")
    if not frames[state["frame"]]:
        grid.style.gridTemplateColumns = ""
        grid.innerHTML = """
        <div class="glass-card rounded-2xl p-8 text-center text-sm text-slate-400">
          まだ記録がありません。<br>検索タブから曲を登録しましょう。
        </div>"""
        return
    # 高さは制限せずスクロールさせ、カードの大きさは横幅で決める
    # （タブが非表示で幅が測れないときは、枠タブを開いたときに描き直す）
    if grid.clientWidth:
        fill_grid(grid, grid.clientWidth, math.inf)


# ---------- 表示モード ----------

def render_display():
    if el("display").classList.contains("hidden"):
        return
    name = state["frame"]
    el("display-rating").textContent = fmt(frames["total"])
    el("display-rating").setAttribute("data-tier", rating_tier(frames["total"]))
    # 通常画面のヘッダーと同じ箱。表示中の枠を強調し、箱のタップで切り替え
    el("display-frame").innerHTML = stats_boxes(current=name)
    grid = el("display-grid")
    if not frames[name]:
        grid.style.gridTemplateColumns = ""
        grid.innerHTML = '<div class="text-sm text-slate-500 py-8">この枠にはまだ曲がありません</div>'
        return
    wrap = el("display-wrap")
    # 50曲埋まっている枠は上下中央、曲が少ない枠は上詰め
    wrap.style.alignItems = "center" if len(frames[name]) >= DISPLAY_SLOTS else "flex-start"
    fill_grid(grid, wrap.clientWidth, wrap.clientHeight)


window.addEventListener("resize", create_proxy(lambda *_: render_display()))


@when("click", "#display-open")
def on_display_open(event):
    el("display").classList.remove("hidden")
    render_display()


@when("click", "#display-close")
def on_display_close(event):
    el("display").classList.add("hidden")


@when("click", "#display-frame")
def on_display_frame(event):
    box = event.target.closest("[data-frame]")
    if box is None:
        return
    state["frame"] = box.getAttribute("data-frame")
    render_header()
    render_frames()
    render_display()


# ---------- 画像保存 ----------

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
        cards.append({
            "no": i, "title": c["title"], "diff": c["diff"], "const": c["const"], "value": fmt(val),
            "score": score, "rank": get_rank(score) if score else "",
            "medals": [] if plat else lamp_medals(rec),
            "stars": rec.get("star", 0) if plat else None,
            "jacket": jacket_url(c),
        })
    header = {
        "rating": fmt(frames["total"]), "tier": rating_tier(frames["total"]),
        "stats": [(label, f"{len(frames[key])}/{FRAME_META[key][1]}", f"{floor4(value):.4f}", key == name)
                  for key, label, value in stats_items()],
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
                                         js_obj({"type": "image/png"}))
    el("snap-img").src = url
    el("snap-modal").classList.remove("hidden")


@when("click", "#snap-close")
def on_snap_close(event):
    el("snap-modal").classList.add("hidden")


@when("click", "#snap-share")
def on_snap_share(event):
    file = state.get("snap_file")
    if file is not None:
        share_or_download(file, el("snap-img").src,
                          lambda: toast("共有できませんでした。画像を長押しして保存してください", error=True))
