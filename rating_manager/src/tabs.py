"""下部タブの切り替え

各画面のモジュールは @on_show("search") のように、タブを開いたときの描画処理を登録する。
（画面同士が互いを import し合わないよう、ここを経由して呼ぶ）
"""
from pyscript import document, window

from store import state

_renderers = {}


def on_show(name):
    def register(fn):
        _renderers[name] = fn
        return fn
    return register


def show_tab(name):
    if name != state["tab"]:
        state["prev_tab"] = state["tab"]
    state["tab"] = name
    for page in document.querySelectorAll(".tab-page"):
        page.classList.toggle("hidden", page.id != f"tab-{name}")
    for btn in document.querySelectorAll(".nav-btn"):
        btn.classList.toggle("active", btn.getAttribute("data-tab") == name)
    if name in _renderers:
        _renderers[name]()
    window.scrollTo(0, 0)
