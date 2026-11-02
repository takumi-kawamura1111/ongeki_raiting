"""アプリのデータ（譜面・記録・レートの推移・手動追加の曲・画面の状態）と、その読み込み・保存

他のモジュールは `from store import charts, records, ...` で同じオブジェクトを共有する。
どれも作り直さず中身を書き換えて使うこと（frames も clear/update で更新する）
"""
import json

from pyodide.http import pyfetch
from pyscript import window

from custom import replace_with_official, song_charts
from dom import el, js_obj, normalize, storage_get, storage_set, today_str
from history import GRANULARITIES
from rating import compute_frames

DATA_URL = "https://reiwa.f5.si/ongeki_record.json"
DATA_CACHE = "ongeki-rm-data"

# localStorage のキー
STORE_RECORDS = "ongeki_rm_records"
STORE_NEW_VERSIONS = "ongeki_rm_new_versions"
STORE_HISTORY = "ongeki_rm_history"
STORE_GRAN = "ongeki_rm_graph_gran"
STORE_LATEST_VERSION = "ongeki_rm_latest_version"
STORE_SHORT_INPUT = "ongeki_rm_short_input"
STORE_CUSTOM = "ongeki_rm_custom"
STORE_DATA_MODIFIED = "ongeki_rm_data_modified"

charts = {}          # "id:diff" -> 譜面データ
versions = []        # 古い順
records = {}         # "id:diff" -> {"score", "fb", "fc", "ab", "star"}
rating_history = {}  # "YYYY-MM-DD" -> その日の最終的な総合レート
custom_songs = []    # 手動で追加した曲（custom.py の形式）
new_versions = set()
frames = {}          # rating.compute_frames の結果
state = {"frame": "best", "selected": None, "diff": "ALL", "star": 0, "lamp": "none", "calc_lamp": "none",
         "tab": "frames", "prev_tab": "frames", "short_input": True, "gran": "day", "chart_points": []}


def version_label(v: str) -> str:
    return v or "オンゲキ"


# ---------- 保存 ----------

def save_records():
    storage_set(STORE_RECORDS, json.dumps(records, ensure_ascii=False))


def save_custom():
    storage_set(STORE_CUSTOM, json.dumps(custom_songs, ensure_ascii=False))


def save_history():
    storage_set(STORE_HISTORY, json.dumps(rating_history))


def save_new_versions():
    storage_set(STORE_NEW_VERSIONS, json.dumps(sorted(new_versions), ensure_ascii=False))


# ---------- 楽曲データ ----------

async def fetch_chart_text() -> str:
    """
    楽曲データ（約1.2MB）は配信元で更新されたときだけ取り直し、それ以外は端末に保存したものを使う。
    更新の有無は本体を落とさずに HEAD で更新日時（Last-Modified）だけ見て判断する。
    オフラインなどで確認できないときも、保存したデータがあればそれで起動する
    """
    try:
        cache = await window.caches.open(DATA_CACHE)
    except Exception:
        cache = None  # Cache API が使えない環境では毎回取得する
    try:
        head = await window.fetch(DATA_URL, js_obj({"method": "HEAD", "cache": "no-store"}))
        modified = head.headers.get("last-modified")
    except Exception:
        modified = None
    if cache is not None:
        cached = await cache.match(DATA_URL)
        if cached is not None and (modified is None or modified == storage_get(STORE_DATA_MODIFIED)):
            return await cached.text()
    el("loader-msg").textContent = "楽曲データを更新中…"
    resp = await pyfetch(DATA_URL)
    text = await resp.string()
    if cache is not None and resp.ok:
        await cache.put(DATA_URL, window.Response.new(text))
        storage_set(STORE_DATA_MODIFIED, modified or "")
    return text


async def load_charts():
    raw = json.loads((await fetch_chart_text()).lstrip("﻿"))
    first_release = {}
    for c in raw:
        key = f"{c['id']}:{c['diff']}"
        c["key"] = key
        c["search"] = normalize(f"{c['title']} {c['artist']}")
        charts[key] = c
        v = c["version"]
        first_release[v] = min(first_release.get(v, c["release_unix"]), c["release_unix"])
    versions.extend(sorted(first_release, key=first_release.get))


def load_storage():
    """保存してある記録・設定を読み込む。起動時に楽曲データの後で呼ぶ"""
    try:
        records.update(json.loads(storage_get(STORE_RECORDS) or "{}"))
    except ValueError:
        pass
    saved = storage_get(STORE_NEW_VERSIONS)
    latest, known = versions[-1], storage_get(STORE_LATEST_VERSION)
    if saved is not None and (known is None or known == latest):
        new_versions.update(v for v in json.loads(saved) if v in versions)
    else:
        # 初回、またはデータに新しいバージョンが現れたら、新曲枠をそのバージョンに切り替える
        new_versions.add(latest)
        save_new_versions()
        if saved is not None:
            state["version_notice"] = latest
    storage_set(STORE_LATEST_VERSION, latest)
    try:
        rating_history.update(json.loads(storage_get(STORE_HISTORY) or "{}"))
    except ValueError:
        pass
    # 下4桁入力は既定でオン。自分でオフにした場合だけ "0" が保存されている
    state["short_input"] = storage_get(STORE_SHORT_INPUT) != "0"
    if storage_get(STORE_GRAN) in GRANULARITIES:
        state["gran"] = storage_get(STORE_GRAN)
    try:
        songs = json.loads(storage_get(STORE_CUSTOM) or "[]")
    except ValueError:
        songs = []
    replaced = apply_custom(songs)
    if replaced:
        state["custom_notice"] = replaced


def apply_custom(songs) -> int:
    """
    手動追加の曲を譜面一覧に反映する。公式データに同じ曲名・難易度が載った譜面は
    記録ごと公式の譜面に置き換え、手動追加から外す。戻り値は置き換えた譜面数
    """
    for key in [k for k, c in charts.items() if c.get("custom")]:
        del charts[key]
    remaining, replaced = replace_with_official(songs, charts, records)
    custom_songs[:] = remaining
    for song in remaining:
        charts.update(song_charts(song))
    if replaced:
        save_records()
    save_custom()
    return replaced


# ---------- レート ----------

def recompute():
    """記録から各枠と総合レートを計算し直し、今日のレートを推移に残す"""
    frames.clear()
    frames.update(compute_frames(charts, records, new_versions))
    record_history()


def record_history():
    """今日の総合レートを履歴に残す（1日1件、その日の最後の値で上書き）"""
    if not records:
        return
    day, total = today_str(), frames["total"]
    if rating_history.get(day) != total:
        rating_history[day] = total
        save_history()


# ---------- 書き出し・読み込み ----------

def export_text():
    return json.dumps({"records": records, "new_versions": sorted(new_versions), "history": rating_history,
                       "custom": custom_songs}, ensure_ascii=False, indent=1)


def parse_import(text):
    """書き出したデータを読む。形式が違えば ValueError。戻り値は (データ全体, 記録)"""
    try:
        data = json.loads(text)
        imported = data["records"]
    except (KeyError, TypeError) as e:
        raise ValueError from e
    if not isinstance(imported, dict):
        raise ValueError
    return data, imported


def restore(data, imported):
    """parse_import の結果で、今の記録を置き換える"""
    records.clear()
    records.update(imported)
    # 手動追加の曲がある書き出しデータなら、曲も入れ替える（その後公式データとの置き換えも行う）
    if isinstance(data.get("custom"), list):
        apply_custom(data["custom"])
    if isinstance(data.get("history"), dict):
        rating_history.update(data["history"])
        save_history()
    if data.get("new_versions"):
        new_versions.clear()
        new_versions.update(v for v in data["new_versions"] if v in versions)
        save_new_versions()
    save_records()


def clear_all():
    records.clear()
    rating_history.clear()
    save_history()
    save_records()
