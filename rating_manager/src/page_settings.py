"""設定タブ（新曲枠のバージョン、手動で追加した曲、データの書き出し・読み込み）"""
import html

from pyodide.ffi import to_js
from pyscript import document, when, window

from dom import el, js_obj, share_or_download, then, toast
from page_frames import recalc
from parts import DIFF_STYLE, DIFFS
from store import (apply_custom, clear_all, custom_songs, export_text, new_versions, parse_import, records, restore,
                   save_new_versions, save_records, state, version_label, versions)
from tabs import on_show

CUSTOM_JACKET_SIZE = 256  # 手動追加の曲のジャケットは正方形に切り抜いてこの大きさで保存する
EXPORT_NAME = "ongeki_rating_records.json"


@on_show("settings")
def render_settings():
    items = []
    for v in reversed(versions):
        checked = "checked" if v in new_versions else ""
        items.append(f"""
        <label class="flex items-center gap-2 p-2 rounded-lg bg-slate-900/60 border border-slate-800 text-xs cursor-pointer">
          <input type="checkbox" class="version-cb w-4 h-4 accent-cyan-400" value="{html.escape(v)}" {checked}>
          {html.escape(version_label(v))}
        </label>""")
    el("version-list").innerHTML = "".join(items)
    el("record-count").textContent = f"登録済み：{len(records)}譜面"
    render_custom_list()


@when("change", "#version-list")
def on_version_change(event):
    new_versions.clear()
    for cb in document.querySelectorAll(".version-cb"):
        if cb.checked:
            new_versions.add(cb.value)
    save_new_versions()
    recalc()


# ---------- 手動で追加した曲 ----------

def render_custom_list():
    if not custom_songs:
        el("custom-list").innerHTML = '<div class="text-xs text-slate-500">まだありません</div>'
        return
    rows = []
    for song in custom_songs:
        diffs = " ".join(
            f'<span class="font-black px-1 rounded {DIFF_STYLE[d][1]}">{d} {const:.1f}</span>'
            for d, const in sorted(song["diffs"].items(), key=lambda kv: DIFFS.index(kv[0])))
        img = (f'<img src="{song["img"]}" alt="" class="w-full h-full object-cover">' if song.get("img") else "")
        rows.append(f"""
        <div class="flex items-center gap-2 p-1.5 rounded-lg bg-slate-900/60 border border-slate-800">
          <div class="w-10 h-10 shrink-0 rounded-sm overflow-hidden bg-slate-800">{img}</div>
          <div class="flex-1 min-w-0">
            <div class="text-xs font-bold truncate">{html.escape(song["title"])}</div>
            <div class="text-[9px] flex flex-wrap gap-1 mt-0.5">{diffs}</div>
          </div>
          <button data-edit="{song["id"]}" class="text-slate-400 text-sm px-2 py-1" aria-label="編集"><i class="fa-solid fa-pen"></i></button>
          <button data-del="{song["id"]}" class="text-rose-400 text-sm px-2 py-1" aria-label="削除"><i class="fa-solid fa-trash"></i></button>
        </div>""")
    el("custom-list").innerHTML = "".join(rows)


def open_custom_form(song=None):
    """song を渡すと編集、None なら新規追加"""
    state["custom_edit"] = song["id"] if song else None
    state["custom_img"] = song.get("img", "") if song else ""
    el("custom-title").value = song["title"] if song else ""
    el("custom-artist").value = song.get("artist", "") if song else ""
    el("custom-version").innerHTML = "".join(
        f'<option value="{html.escape(v)}">{html.escape(version_label(v))}</option>' for v in reversed(versions))
    el("custom-version").value = song["version"] if song else versions[-1]
    for d in DIFFS:
        const = song["diffs"].get(d) if song else None
        el(f"custom-const-{d}").value = f"{const:.1f}" if const is not None else ""
    render_custom_preview()
    el("custom-form").classList.remove("hidden")
    el("custom-new").classList.add("hidden")
    el("custom-form").scrollIntoView(js_obj({"block": "center"}))


def close_custom_form():
    el("custom-form").classList.add("hidden")
    el("custom-new").classList.remove("hidden")


def render_custom_preview():
    img = state["custom_img"]
    el("custom-preview").innerHTML = (
        f'<img src="{img}" alt="" class="w-full h-full object-cover">' if img
        else '<i class="fa-solid fa-image text-slate-600 text-2xl"></i>')


@when("click", "#custom-new")
def on_custom_new(event):
    open_custom_form()


@when("click", "#custom-cancel")
def on_custom_cancel(event):
    close_custom_form()


@when("click", "#custom-list")
def on_custom_list(event):
    btn = event.target.closest("[data-edit], [data-del]")
    if btn is None:
        return
    song_id = btn.getAttribute("data-edit") or btn.getAttribute("data-del")
    song = next((s for s in custom_songs if s["id"] == song_id), None)
    if song is None:
        return
    if btn.hasAttribute("data-edit"):
        open_custom_form(song)
        return
    if not window.confirm(f"「{song['title']}」と、その記録を削除します。よろしいですか？"):
        return
    for d in song["diffs"]:
        records.pop(f"{song_id}:{d}", None)
    save_records()
    apply_custom([s for s in custom_songs if s["id"] != song_id])
    recalc()
    render_settings()
    toast("削除しました")


@when("change", "#custom-jacket")
async def on_custom_jacket(event):
    file = event.target.files.item(0)
    event.target.value = ""
    if file is None:
        return
    try:
        bitmap = await window.createImageBitmap(file)
    except Exception:
        toast("画像を読み込めませんでした", error=True)
        return
    # 中央を正方形に切り抜いて縮小し、JPEG で保存する（ブラウザの保存容量を圧迫しないように）
    side = min(bitmap.width, bitmap.height)
    canvas = document.createElement("canvas")
    canvas.width = canvas.height = CUSTOM_JACKET_SIZE
    canvas.getContext("2d").drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side,
                                      0, 0, CUSTOM_JACKET_SIZE, CUSTOM_JACKET_SIZE)
    state["custom_img"] = canvas.toDataURL("image/jpeg", 0.85)
    render_custom_preview()


@when("click", "#custom-save")
def on_custom_save(event):
    title = el("custom-title").value.strip()
    if not title:
        toast("曲名を入力してください", error=True)
        return
    diffs = {}
    for d in DIFFS:
        text = el(f"custom-const-{d}").value.strip()
        if not text:
            continue
        try:
            const = round(float(text), 1)
        except ValueError:
            const = 0
        if not 1 <= const <= 16:
            toast(f"{d} の定数は 1.0〜16.0 で入力してください", error=True)
            return
        diffs[d] = const
    if not diffs:
        toast("どれか1つ以上の難易度の定数を入力してください", error=True)
        return
    song_id = state.get("custom_edit") or f"c{int(window.Date.now())}"
    old = next((s for s in custom_songs if s["id"] == song_id), None)
    if old:
        # 定数を消した難易度の記録は消す
        for d in set(old["diffs"]) - set(diffs):
            records.pop(f"{song_id}:{d}", None)
        save_records()
    song = {"id": song_id, "title": title, "artist": el("custom-artist").value.strip(),
            "version": el("custom-version").value, "diffs": diffs, "img": state["custom_img"]}
    songs = [song if s["id"] == song_id else s for s in custom_songs] if old else custom_songs + [song]
    replaced = apply_custom(songs)
    recalc()
    close_custom_form()
    render_settings()
    toast("公式の定数表に載っていたため、そちらに置き換えました" if replaced else
          ("保存しました" if old else "追加しました。検索タブから記録を登録できます"))


# ---------- データ管理 ----------

@when("click", "#export-btn")
def on_export(event):
    data = export_text()
    file = window.File.new(to_js([data]), EXPORT_NAME, js_obj({"type": "application/json"}))
    share_or_download(file, "data:application/json;charset=utf-8," + window.encodeURIComponent(data),
                      lambda: toast("書き出しに失敗しました。「コピー」をお試しください", error=True))


@when("click", "#copy-btn")
def on_copy(event):
    then(window.navigator.clipboard.writeText(export_text()),
         lambda *_: toast("クリップボードにコピーしました"),
         lambda *_: toast("コピーできませんでした", error=True))


@when("click", "#paste-btn")
def on_paste(event):
    then(window.navigator.clipboard.readText(),
         import_text,
         lambda *_: toast("クリップボードを読み取れませんでした", error=True))


@when("change", "#import-file")
async def on_import(event):
    file = event.target.files.item(0)
    event.target.value = ""
    if file is None:
        return
    import_text(await file.text())


def import_text(text):
    try:
        data, imported = parse_import(text)
    except ValueError:
        toast("データの形式が正しくありません", error=True)
        return
    if not window.confirm(f"{len(imported)}譜面の記録を読み込みます。現在の記録は上書きされます。"):
        return
    restore(data, imported)
    recalc()
    render_settings()
    toast("読み込みました")


@when("click", "#clear-btn")
def on_clear(event):
    if records and window.confirm("全ての記録（レートの推移を含む）を削除します。よろしいですか？"):
        clear_all()
        recalc()
        render_settings()
        toast("全記録を削除しました")
