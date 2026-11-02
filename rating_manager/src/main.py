"""起動処理。各画面のモジュールを読み込み（イベントの登録）、データを読み込んで最初の画面を描く

モジュールの構成
  計算（画面に依存しない。tests/ でテスト）
    rating.py    レートの計算         history.py  推移グラフの集計     custom.py  手動追加の曲
  共通
    dom.py       ブラウザ操作の小物   store.py    データと保存         parts.py   表示部品
    tabs.py      タブの切り替え       score_input.py  スコアの下4桁入力  snapshot.py  画像保存の描画
  画面
    page_frames.py    上部のレート・枠タブ・表示モード    page_search.py  検索タブ
    page_editor.py    入力画面    page_graph.py  グラフタブ    page_calc.py  計算タブ
    page_settings.py  設定タブ
"""
from pyscript import when

import page_calc  # noqa: F401  （各画面のイベントを登録するために読み込む）
import page_editor  # noqa: F401
import page_graph  # noqa: F401
import page_search  # noqa: F401
import page_settings  # noqa: F401
from dom import el, toast
from page_frames import recalc
from score_input import apply_short_input
from store import load_charts, load_storage, state, version_label
from tabs import show_tab


@when("click", ".nav-btn, .nav-jump")
def on_nav(event):
    show_tab(event.currentTarget.getAttribute("data-tab"))


el("loader-msg").textContent = "楽曲データを確認中…"
try:
    await load_charts()
    load_storage()
    recalc()
    apply_short_input()
    if state.get("version_notice"):
        toast(f"新バージョン「{version_label(state['version_notice'])}」を新曲枠に設定しました")
    elif state.get("custom_notice"):
        toast(f"手動で追加した{state['custom_notice']}譜面を、公式の定数表のデータに置き換えました")
    el("loader").classList.add("hidden")
except Exception as e:
    el("loader-msg").textContent = f"楽曲データの取得に失敗しました：{e}"
