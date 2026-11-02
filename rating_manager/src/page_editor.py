"""入力画面（譜面のジャケットをタップして開く、スコア・ランプ・★の登録）"""
import html

from pyscript import when, window

from dom import el, fmt, toast
from page_frames import recalc
from parts import DIFF_STYLE, DIFFS, LAMPS, THEORETICAL_LAMP, THEORETICAL_SCORE, jacket_url, lamp_of, render_lamps
from rating import parse_score, plat_rating, single_rating, total_if
from score_input import on_mode_change, update_score_hint
from store import charts, frames, new_versions, records, save_records, state, version_label
from tabs import show_tab

STAR_LABELS = ["0", "1", "2", "3", "4", "5", "虹"]


def open_editor(key):
    c = charts.get(key)
    if c is None:
        return
    state["selected"] = key
    rec = records.get(key, {})
    jacket = jacket_url(c)
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
    render_lamps("ed-lamps", state["lamp"])
    render_stars()
    update_preview()
    show_tab("input")


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


@on_mode_change
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


@when("click", "#frame-grid, #search-grid, #ed-diffs")
def on_card(event):
    card = event.target.closest("[data-key]")
    if card:
        open_editor(card.getAttribute("data-key"))


@when("click", "#ed-back")
def on_editor_back(event):
    show_tab(state["prev_tab"] if state["prev_tab"] != "input" else "frames")


@when("click", ".quick-score")
def set_quick_score(event):
    score = event.currentTarget.getAttribute("data-score")
    el("ed-score").value = score
    if int(score) == THEORETICAL_SCORE:
        state["lamp"] = THEORETICAL_LAMP
        render_lamps("ed-lamps", state["lamp"])
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
        render_lamps("ed-lamps", state["lamp"])
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
