# オンゲキ レート管理

PyScript で動くレート管理アプリ。GitHub Pages で公開している。

## フォルダ構成

```
rating_manager/
├── index.html        画面（HTML と Tailwind のクラス）。src/ の .py を読み込む
├── ongeki_net.js     オンゲキネットで実行するスクリプト（ブックマークレットから読み込み、記録をコピーする）
├── assets/           アイコン画像
├── src/              Python
│   ├── main.py       起動処理
│   ├── rating.py     レートの計算          ┐
│   ├── history.py    推移グラフの集計      ├ 画面に依存しない計算（tests/ でテスト）
│   ├── custom.py     手動追加の曲          │
│   ├── updates.py    更新日と NEW 表示の判定 │
│   ├── ongeki_net.py オンゲキネットの記録の取り込み ┘
│   ├── store.py      データと保存（記録・推移・楽曲データの取得とキャッシュ）
│   ├── dom.py        ブラウザ操作の共通処理
│   ├── parts.py      複数の画面で使う表示部品
│   ├── tabs.py       タブの切り替え
│   ├── score_input.py スコアの下4桁入力
│   ├── snapshot.py   枠・グラフの画像保存（Canvas 描画）
│   └── page_*.py     各画面（frames / search / editor / graph / calc / settings）
└── tests/            src/ の計算部分のテスト
```

新しく .py を `src/` に足したときは、`index.html` 末尾の `<script type="py">` の `files` にも追加する。

## テスト

```
cd rating_manager
python -m unittest
```
