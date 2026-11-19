/*
 * オンゲキネットの記録をレート管理に取り込むためのスクリプト。
 * オンゲキネット（ongeki-net.com）にログインした状態で、ブックマークレットから読み込んで実行する。
 *
 * 全ジャンルの楽曲別レコードを難易度ごとに読み、プレイ済みの譜面の
 * テクニカルスコア・ランプ・プラチナスコアをまとめて JSON にし、クリップボードにコピーする。
 * レート管理の設定タブで「貼り付けて取り込み」を押すと反映される（src/ongeki_net.py）。
 *
 * 形式: {"ongeki_net": 1, "date": "YYYY-MM-DD", "songs": [
 *   {"t": 曲名, "d": "MAS", "l": "14+", "g": ジャンル, "s": スコア, "fb": 0/1, "fc": 0/1, "ab": 0/1,
 *    "p": [プラチナスコア, 最大] または null, "h": 曲名が重複する譜面だけ、詳細ページの本文（アーティストの照合用）}
 * ]}
 */
(() => {
  "use strict";
  const BASE = "https://ongeki-net.com/ongeki-mobile/record/";
  const DIFFS = [["BAS", 0, "BASIC"], ["ADV", 1, "ADVANCED"], ["EXP", 2, "EXPERT"], ["MAS", 3, "MASTER"], ["LUN", 10, "LUNATIC"]];
  const WAIT_MS = 1500; // オンゲキネットに負担をかけないよう、ページを読む間隔を空ける

  if (location.hostname !== "ongeki-net.com") {
    alert("オンゲキネット（ongeki-net.com）にログインした状態で実行してください");
    return;
  }
  if (document.getElementById("rm-net-overlay")) return; // 二重に実行しない

  // ---------- 画面（オンゲキネットの上に重ねる） ----------
  const overlay = document.createElement("div");
  overlay.id = "rm-net-overlay";
  overlay.style.cssText = "position:fixed;inset:0;z-index:2147483647;background:rgba(2,6,23,.92);color:#e2e8f0;" +
    "display:flex;align-items:center;justify-content:center;padding:16px;font:14px/1.6 sans-serif;";
  const box = document.createElement("div");
  box.style.cssText = "width:100%;max-width:360px;background:#0f172a;border:1px solid #334155;border-radius:16px;" +
    "padding:20px;text-align:center;";
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  const button = (label, primary) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.style.cssText = "display:block;width:100%;margin-top:10px;padding:12px;border-radius:12px;font-weight:bold;" +
      "font-size:14px;border:1px solid #334155;" +
      (primary ? "background:linear-gradient(90deg,#22d3ee,#f472b6);color:#0f172a;border:none;" : "background:#1e293b;color:#e2e8f0;");
    return b;
  };
  const show = (html) => { box.innerHTML = `<div style="font-weight:bold;margin-bottom:8px">レート管理に取り込み</div>${html}`; };
  const close = () => overlay.remove();

  // ---------- 読み込みと解析 ----------
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const num = (s) => parseInt(String(s).replace(/[^\d]/g, ""), 10) || 0;

  async function getDoc(url) {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok || res.url.includes("/error")) throw new Error("login");
    return new DOMParser().parseFromString(await res.text(), "text/html");
  }

  function parseList(doc, diff) {
    const songs = [];
    let genre = "";
    // ジャンルの見出しと曲の枠が文書順に並んでいる
    for (const node of doc.querySelectorAll("div.p_5.f_20, div.basic_btn")) {
      if (!node.classList.contains("basic_btn")) {
        genre = node.textContent.trim();
        continue;
      }
      const title = node.querySelector(".music_label");
      const values = [...node.querySelectorAll("td.score_value")].map((td) => td.textContent.trim());
      if (!title || values.length < 3) continue; // 未プレイ
      const icons = [...node.querySelectorAll(".music_score_icon_area img")]
        .map((img) => (img.getAttribute("src").match(/music_icon_(\w+)\.png/) || [])[1]);
      const plat = (node.querySelector(".platinum_high_score_text_block")?.textContent || "").match(/([\d,]+)\s*\/\s*([\d,]+)/);
      const idx = node.querySelector('input[name="idx"]');
      songs.push({
        t: title.textContent.trim(), d: diff, l: (node.querySelector(".score_level")?.textContent || "").trim(), g: genre,
        s: num(values[2]),
        fb: icons.includes("fb") ? 1 : 0, fc: icons.includes("fc") ? 1 : 0,
        ab: icons.includes("ab") || icons.includes("abplus") ? 1 : 0,
        p: plat ? [num(plat[1]), num(plat[2])] : null,
        idx: idx ? idx.value : "",
      });
    }
    return songs;
  }

  async function run() {
    const all = [];
    for (let i = 0; i < DIFFS.length; i++) {
      const [diff, value, label] = DIFFS[i];
      show(`${label} を読み込み中…（${i + 1}/${DIFFS.length}）`);
      if (i) await sleep(WAIT_MS);
      const doc = await getDoc(`${BASE}musicGenre/search/?genre=99&diff=${value}`);
      const songs = parseList(doc, diff);
      if (!songs.length && !doc.querySelector("div.basic_btn")) throw new Error("page");
      all.push(...songs);
    }
    // 同じ難易度に同じ曲名が複数ある譜面（Singularity など）は、詳細ページを読んでアーティストで見分けられるようにする
    const count = {};
    for (const s of all) count[s.d + "\n" + s.t] = (count[s.d + "\n" + s.t] || 0) + 1;
    const dups = all.filter((s) => count[s.d + "\n" + s.t] > 1 && s.idx);
    for (let i = 0; i < dups.length; i++) {
      show(`同じ曲名の譜面を確認中…（${i + 1}/${dups.length}）`);
      await sleep(WAIT_MS);
      try {
        const doc = await getDoc(`${BASE}musicDetail/?idx=${encodeURIComponent(dups[i].idx)}`);
        dups[i].h = (doc.querySelector(".container3") || doc.body).textContent.replace(/\s+/g, " ").slice(0, 8000);
      } catch (e) { /* 見分けられなかった譜面は取り込み側で飛ばす */ }
    }
    for (const s of all) delete s.idx;
    const d = new Date();
    const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return JSON.stringify({ ongeki_net: 1, date, songs: all });
  }

  function done(text, n) {
    show(`<div>${n}譜面の記録を取得しました。</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:6px">下のボタンでコピーしてから、レート管理の設定タブで<br>「貼り付けて取り込み」を押してください。</div>`);
    const copy = button("コピー", true);
    const quit = button("閉じる", false);
    copy.onclick = () => {
      navigator.clipboard.writeText(text).then(
        () => { copy.textContent = "コピーしました"; },
        () => {
          // コピーできない環境では、全選択した文字欄を出して手でコピーしてもらう
          const ta = document.createElement("textarea");
          ta.value = text;
          ta.readOnly = true;
          ta.style.cssText = "width:100%;height:120px;margin-top:10px;font-size:11px;color:#0f172a;";
          box.insertBefore(ta, quit);
          ta.focus();
          ta.select();
          copy.textContent = "自動でコピーできませんでした。下の欄を全選択してコピーしてください";
        });
    };
    quit.onclick = close;
    box.append(copy, quit);
  }

  run().then((text) => done(text, JSON.parse(text).songs.length), (e) => {
    show(e.message === "login"
      ? "オンゲキネットにログインしていないか、ログインの期限が切れています。ログインし直してから実行してください。"
      : `記録を読み込めませんでした（${e.message}）。時間をおいて試してください。`);
    const quit = button("閉じる", false);
    quit.onclick = close;
    box.appendChild(quit);
  });
})();
