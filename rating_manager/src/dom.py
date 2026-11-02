"""ブラウザ操作の小さな共通処理（要素の取得、トースト、localStorage など）"""
import unicodedata

from pyodide.ffi import create_once_callable, to_js
from pyscript import document, window


def el(id_):
    return document.getElementById(id_)


def js_obj(d):
    """Python の dict を JavaScript のオブジェクトにする（fetch のオプションなど）"""
    return to_js(d, dict_converter=window.Object.fromEntries)


def normalize(s: str) -> str:
    return unicodedata.normalize("NFKC", s).lower()


def fmt(v: float) -> str:
    return f"{v:.3f}"


def today_str():
    d = window.Date.new()
    return f"{d.getFullYear():04d}-{d.getMonth() + 1:02d}-{d.getDate():02d}"


def toast(msg, error=False):
    t = el("toast")
    t.textContent = msg
    t.classList.toggle("bg-rose-500/90", error)
    t.classList.toggle("bg-cyan-500/90", not error)
    t.classList.remove("opacity-0", "translate-y-2")
    window.clearTimeout(getattr(toast, "timer", 0))
    hide = create_once_callable(lambda *_: t.classList.add("opacity-0", "translate-y-2"))
    toast.timer = window.setTimeout(hide, 1800)


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


def set_active(selector, attr, value):
    """selector に当たるボタンのうち、attr が value のものだけ active にする"""
    for b in document.querySelectorAll(selector):
        b.classList.toggle("active", b.getAttribute(attr) == value)


def then(promise, on_ok, on_err):
    """Safariはタップ処理中に同期で呼ばないと共有・クリップボードを拒否するため、awaitせずに結果を受け取る"""
    promise.then(create_once_callable(on_ok), create_once_callable(on_err))


def share_or_download(file, href, on_share_error):
    """
    ファイルを共有シートで渡す（iOSのホーム画面アプリではダウンロードリンクが動かないため）。
    共有できない環境では href をダウンロードさせる
    """
    payload = js_obj({"files": [file]})
    nav = window.navigator
    if hasattr(nav, "canShare") and nav.canShare(payload):
        def on_err(e):
            if getattr(e, "name", "") != "AbortError":
                on_share_error()
        then(nav.share(payload), lambda *_: None, on_err)
        return
    a = document.createElement("a")
    a.href = href
    a.download = file.name
    a.click()
