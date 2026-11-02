"""スコア入力欄の「下4桁」入力（入力画面と計算タブで共通）"""
from pyscript import document, when

from dom import el, storage_set
from parts import RANK_COLOR
from rating import get_rank, parse_score
from store import STORE_SHORT_INPUT, state

# 下4桁入力の切り替え時に、入力値を読み直してほしい処理（入力画面のプレビュー、計算タブの結果）
_listeners = []


def on_mode_change(fn):
    _listeners.append(fn)
    return fn


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
    for fn in _listeners:
        fn()


@when("input", ".score-input")
def on_score_input(event):
    update_score_hint(event.currentTarget.id)


@when("focus", ".score-input")
def on_score_focus(event):
    # 下4桁入力のときは、タップしてすぐ打ち直せるよう全選択する
    if state["short_input"]:
        event.currentTarget.select()
