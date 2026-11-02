"""計算タブ（定数・スコア・ランプから単曲レートを計算。旧 rating_calc）"""
from pyscript import when

from dom import el, fmt
from parts import LAMPS, RANK_COLOR, THEORETICAL_LAMP, THEORETICAL_SCORE, render_lamps
from rating import calc_lamp_bonus, calc_score_rating, get_rank, parse_score, single_rating
from score_input import on_mode_change, update_score_hint
from store import state
from tabs import on_show


@on_show("calc")
def show_calc():
    render_lamps("calc-lamps", state["calc_lamp"])
    update_calc()


@on_mode_change
def update_calc():
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
