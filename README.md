# 日本の世界遺産・国宝建造物マップ

国内の **世界遺産**（金）・ **世界遺産暫定リスト**（銀）・ **国宝建造物**（銅）の場所を OpenStreetMap 上にピン表示し、都道府県ごとのポイントランキングを作る Web アプリです。コメリ全店舗マップと同じ技術スタック（Leaflet + OpenStreetMap + markercluster、静的 JSON、vanilla JS、GitHub Pages）を踏襲しています。

## 機能

- 3種別をピン色で識別：**世界遺産=金**・**暫定リスト=銀**・**国宝建造物=銅**
  - 暫定リストは「公式暫定リスト」と「暫定リスト記載候補」（文化庁審議27件）を色味で区別
  - 「飛鳥・藤原の宮都とその関連資産群」（奈良県）は2026年7月に世界遺産登録されたため世界遺産（金）として扱う
- **種別フィルタ**（世界遺産 / 公式暫定 / 暫定候補 / 国宝）と **カテゴリフィルタ**（文化遺産 / 自然遺産 / 混合遺産）を組み合わせて表示
- 名称・都道府県で検索、都道府県絞り込み
- サイドバーリスト ⇄ 地図マーカーの連動
- ポップアップから Google Maps 経路・ストリートビュー・検索へリンク
- **都道府県ポイントランキング** タブ

### ポイント集計ルール

| 種別 | ポイント |
|------|----------|
| 世界遺産 | 3 pt |
| 暫定リスト（公式・候補） | 2 pt |
| 国宝建造物 | 1 pt |

- 同じ場所が複数種別に該当する場合は **上位のポイントのみ反映**（例: 姫路城は世界遺産3ptのみカウントし、国宝分は加算しない）
- 複数都道府県にまたがる物件（白神山地=青森・秋田 など）は両方の都道府県にポイントを付与

## 構成

```
.
├── web/                        # 静的Webアプリ（GitHub Pages にデプロイされる）
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── data/
│       └── heritage.json       # 遺産データ（ビルダが生成）
├── crawl/                      # データビルドスクリプト
│   ├── build_heritage.py           # シード（世界遺産・暫定）+ 国宝JSON をマージし Nominatim で座標補完して heritage.json を生成
│   ├── national_treasures.json     # 国宝建造物リスト（facility単位、手元で作成）
│   ├── check_source_updates.py     # 文化庁3ページの変更検知（→ GitHub Issue 作成）
│   ├── source_snapshots/           # 各ページの前回スナップショット（差分表示用）
│   └── source_hashes.json          # 各ページのハッシュ値
└── .github/workflows/
    ├── update-deploy.yml           # push で Pages デプロイ
    └── check-source-updates.yml    # 3ヶ月ごとに情報源の変更をチェックし Issue 化
```

## 実行方法

`web/data/heritage.json` を `fetch()` で読み込むため、ローカルサーバ経由で開いてください（`file://` では動きません）。

```bash
python3 -m http.server 8000
# ブラウザで http://localhost:8000/web/ を開く
```

## データ再生成

```bash
python3 crawl/build_heritage.py    # web/data/heritage.json を生成
```

- 世界遺産27件・暫定候補27件は `build_heritage.py` 内に座標付きで埋め込み済み（公式暫定リストは2026年7月時点で0件）。
- 国宝建造物は `crawl/national_treasures.json`（facility単位）から読み込み、OpenStreetMap の Nominatim で座標を補完（`crawl/geocode_cache.json` にキャッシュ）。

## 情報源

- [文化庁 世界遺産一覧](https://www.bunka.go.jp/seisaku/bunkazai/shokai/sekai_isan/ichiran/)
- [文化庁 世界遺産暫定リスト記載候補（審議結果）](https://www.bunka.go.jp/seisaku/bunkashingikai/bunkazai/sekaitokubetsu/shingi_kekka/besshi_8.html)
- [文化庁 国宝建造物](https://www.bunka.go.jp/seisaku/bunkazai/shokai/yukei_kenzobutsu/kokuho_bunkazai.html)
- 座標: OpenStreetMap Nominatim
- 地図: © OpenStreetMap contributors（[ODbL](https://www.openstreetmap.org/copyright)）

## 情報源の更新チェック

`.github/workflows/check-source-updates.yml` が3ヶ月ごと（1/4/7/10月の1日）に文化庁の3ページ（世界遺産一覧・暫定リスト記載候補・国宝建造物）の本文をチェックし、前回スナップショットとの差分があれば GitHub Issue（ラベル `data-source-update`）を作成・更新します。

- データそのものは自動で書き換えません。世界遺産/暫定リストの区分や国宝建造物のfacility分類は文脈判断が必要なため、Issueを見て人（Claude Codeセッション含む）が `crawl/national_treasures.json` や `build_heritage.py` 内のシードを手動で更新し、`python3 crawl/build_heritage.py` を再実行してください。
- 手動実行: `python3 crawl/check_source_updates.py --dry-run`（Issue作成・コミットはせず結果表示のみ）
- ローカルで初回実行するとスナップショットが `crawl/source_snapshots/` に保存され、以後はそれとの差分で変更を検知します。

## GitHub Pages デプロイ

`.github/workflows/update-deploy.yml` が `web/**` の変更を push するたびに `web/` を `site/` にコピーして Pages にデプロイします（クロール不要・数十秒）。

1. リポジトリを GitHub にプッシュ
2. **Settings → Pages** の **Source** を「GitHub Actions」に設定
3. `https://<ユーザー名>.github.io/<リポジトリ名>/` で公開