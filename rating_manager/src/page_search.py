"""検索タブ（定数表）"""
import html

from pyodide.ffi import create_once_callable, create_proxy
from pyscript import when, window

from dom import el, js_obj, normalize, set_active
from parts import (DIFF_STYLE, SCORE_BAR_EM, fit_score_bars, jacket_bottom, jacket_url, lamp_badge, lamp_fs,
                   score_bar, score_text)
from rating import get_rank
from store import charts, records, state
from tabs import on_show

SEARCH_CHUNK = 180       # 一度に足すカード数（6列×30行）
SEARCH_PRELOAD = 1200    # 画面の下端からこの距離(px)以内に未表示の領域が来たら続きを描く


def parse_float(id_):
    try:
        return float(el(id_).value)
    except ValueError:
        return None


@on_show("search")
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

    def score_and_star(c):
        rec = records.get(c["key"], {})
        return rec.get("score", 0), rec.get("star", 0)

    sort = el("search-sort").value
    if sort == "new":
        hits.sort(key=lambda c: (c["release_unix"], c["const"]), reverse=True)
    else:
        # 同じ定数の中ではスコアが高い順、同点なら★が多い順（未登録は後ろ）
        hits.sort(key=lambda c: (c["const"], *score_and_star(c)), reverse=True)

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
    if not cards:
        state["search_rest"] = []
        grid.innerHTML = '<div class="col-span-6 text-center text-sm text-slate-500 py-8">該当する譜面がありません</div>'
        return
    # 全件（約3500譜面）を一度に描くと重いため、最初は一部だけ描き、スクロールに合わせて足していく
    grid.innerHTML = ""
    state["search_rest"] = cards
    append_search_cards()


def append_search_cards(*_):
    """続きのカードを、画面の下端の少し先まで埋まるだけ足す"""
    grid, more = el("search-grid"), el("search-more")
    added = False
    # 検索タブが非表示のときは位置が測れないため描かない（タブを開いたときに描き直される）
    while state.get("search_rest") and state["tab"] == "search" \
            and more.getBoundingClientRect().top < window.innerHeight + SEARCH_PRELOAD:
        chunk, state["search_rest"] = state["search_rest"][:SEARCH_CHUNK], state["search_rest"][SEARCH_CHUNK:]
        grid.insertAdjacentHTML("beforeend", "".join(chunk))
        added = True
    if added:
        window.setTimeout(create_once_callable(lambda *_: fit_score_bars(grid)), 80)


window.addEventListener("scroll", create_proxy(append_search_cards), js_obj({"passive": True}))


def search_card(c, rec, show_diff, bar_fs):
    """検索結果の小さいカード。定数未確定の譜面は点線枠"""
    ring, badge = DIFF_STYLE[c["diff"]]
    frame = "border-2 border-dashed border-amber-400" if c["is_unknown"] else f"ring-1 {ring}"
    score = rec.get("score", 0)
    bar = score_bar(score_text(score), get_rank(score), bar_fs) if score else ""
    lamp = lamp_badge(rec, lamp_fs(bar_fs))
    # P枠の★：スコアの帯のすぐ上の左（スコア未登録なら下端）に出す
    star = rec.get("star", 0)
    stars = ""
    if star:
        text = "★" * min(star, 5) + ('<span class="text-white"> 虹</span>' if star == 6 else "")
        stars = (f'<span class="px-[0.25em] rounded-r-sm bg-black/80 text-yellow-300 '
                 f'leading-tight whitespace-nowrap" style="font-size:{max(6.0, bar_fs * 0.85):.1f}px">{text}</span>')
    diff_html = (f'<span class="absolute top-0 left-0 text-[7px] font-black px-0.5 rounded-br-sm {badge}">{c["diff"]}</span>'
                 if show_diff else "")
    # スコアも★も未登録（未プレイ）の譜面はジャケットを暗くして、プレイ済みと見分けやすくする
    played = score or rec.get("star", 0)
    dim = "" if played else "brightness-[0.4] saturate-[0.6]"
    title_color = "text-slate-200" if played else "text-slate-500"
    return f"""<button data-key="{c['key']}" class="jacket-card min-w-0 text-left">
      <div class="relative aspect-square rounded-sm overflow-hidden bg-slate-800 {frame}">
        <img loading="lazy" src="{jacket_url(c)}" alt="" class="w-full h-full object-cover {dim}" onerror="this.style.opacity=0">
        {diff_html}{jacket_bottom(stars, lamp, bar)}
      </div>
      <div class="truncate text-[8px] leading-tight {title_color} mt-px">{html.escape(c['title'])}</div>
    </button>"""


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
