"""グラフタブ（総合レートの推移）"""
from pyscript import when

from dom import el, fmt, set_active, storage_set
from history import bucket_label, bucketize, x_ticks, y_range
from store import STORE_GRAN, rating_history, state
from tabs import on_show

CHART_W, CHART_H = 360, 220
CHART_PAD = {"left": 40, "right": 14, "top": 14, "bottom": 26}
CHART_LINE = "#67e8f9"   # cyan-300
CHART_SURFACE = "#121824"


@on_show("graph")
def show_graph():
    set_active(".gran-chip", "data-gran", state["gran"])
    render_graph()


def render_graph():
    gran = state["gran"]
    points = bucketize(rating_history, gran)
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
        rows.append((x_of(o), y_of(v), bucket_label(o, gran), date, v, delta))
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


@when("pointerleave", "#chart")
def on_chart_leave(event):
    if el("chart-tip"):
        el("chart-tip").classList.add("hidden")
        el("chart-cross").setAttribute("visibility", "hidden")
