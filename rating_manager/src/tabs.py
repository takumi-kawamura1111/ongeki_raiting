"""下部タブの切り替え

各画面のモジュールは @on_show("search") のように、タブを開いたときの描画処理を登録する。
（画面同士が互いを import し合わないよう、ここを経由して呼ぶ）
"""
from pyscript import document, window

from store import state

_renderers = {}
_scroll_y = {}  # タブ -> 最後に離れたときのスクロール位置


def on_show(name):
    def register(fn):
        _renderers[name] = fn
        return fn
    return register


def show_tab(name, keep_scroll=False):
    """
    keep_scroll: 前にそのタブを離れたときのスクロール位置に戻す（入力画面から戻るとき用）。
    描画処理は state["scroll_to"] を見て、その位置まで内容を用意しておく
    """
    if name != state["tab"]:
        state["prev_tab"] = state["tab"]
        _scroll_y[state["tab"]] = window.scrollY
    state["tab"] = name
    state["scroll_to"] = _scroll_y.get(name, 0) if keep_scroll else 0
    for page in document.querySelectorAll(".tab-page"):
        page.classList.toggle("hidden", page.id != f"tab-{name}")
    for btn in document.querySelectorAll(".nav-btn"):
        btn.classList.toggle("active", btn.getAttribute("data-tab") == name)
    if name in _renderers:
        _renderers[name]()
    window.scrollTo(0, state["scroll_to"])
