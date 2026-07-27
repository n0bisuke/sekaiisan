# コメリ 全店舗マップ

コメリの全ブランド（コメリ／コメリPRO／コメリパワー／コメリハード＆グリーン／コメリリフォーム）の全国店舗を OpenStreetMap 上に表示する Web アプリです。

## 構成

```
.
├── web/                        # 静的Webアプリ（これがGitHub Pagesにデプロイされる）
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── data/
│       ├── all_stores.json     # 全店舗データ（クローラが生成）
│       └── population.json     # 47都道府県人口（ランキング計算用）
├── crawl/                      # データ収集スクリプト
│   ├── crawl_komeri.py         # 公式店舗検索から全店舗をクロール（並行・キャッシュ付き）
│   ├── fix_names.py            # 未開店店舗の「エラー」名をResultListから復元
│   ├── fill_coords.py          # goo.gl未取得店舗の座標をNominatimで補完
│   ├── crawl_cache.json        # クロールキャッシュ（gitignore対象）
│   └── fill_cache.json         # 座標補完キャッシュ（gitignore対象）
└── .github/workflows/update-deploy.yml   # 定期クロール → Pages デプロイ
```

## 実行方法

`web/data/all_stores.json` を `fetch()` で読み込むため、ローカルサーバ経由で開いてください（`file://` では動きません）。

```bash
cd /Users/nobisuke/ds/2_playground/komeri
python3 -m http.server 8000
```

ブラウザで http://localhost:8000/web/ を開く。

## データ取得手順（`crawl/`）

公式店舗検索 `https://www.komeri.com/shop/storeSearch/CriteriaInput.aspx` から以下を巡回します。

1. 47都道府県ごとに `CriteriaResult.aspx?search={都道府県}` をページ巡回し、エリアグループ（`ResultList.aspx`）のリンクを収集
2. 各 `ResultList.aspx` から `storeDetail.aspx?id={id}` の店舗IDを収集
3. 各 `storeDetail.aspx` から店舗名・住所・電話番号・Google Maps 短縮リンクを取得
4. Google Maps 短縮リンクを展開し `!3d{lat}!4d{lon}` から正確な緯度経度を取得（Nominatim 不使用）

```bash
python3 crawl/crawl_komeri.py    # web/data/all_stores.json を生成。キャッシュで再開可能
python3 crawl/fix_names.py       # エラー名復元
python3 crawl/fill_coords.py     # 座標補完
```

スクリプトは配置場所（`crawl/`）基準でパスを解決するため、リポジトリルートから実行できます。

## 機能

- 全店舗を地図上にマーカー表示（クラスタリング、ブランド別カラー）
- ブランドフィルタ（チェックボックス・店舗数表示）
- 店舗名・住所の部分一致検索
- 都道府県フィルタ
- サイドバーリスト ⇄ 地図マーカーの連動（クリックで移動・ポップアップ）
- ポップアップから店舗詳細ページ・OSM 経路検索へリンク

## データ・ライセンス

- 店舗データ: [コメリ 公式店舗検索](https://www.komeri.com/shop/storeSearch/CriteriaInput.aspx) より抽出
- 座標: 各店舗の Google Maps 短縮リンクを展開して取得（公式店舗詳細ページに埋め込まれたもの）
- 地図: © OpenStreetMap contributors（[ODbL](https://www.openstreetmap.org/copyright)）

## GitHub Actions で定期更新 → GitHub Pages デプロイ

`.github/workflows/update-deploy.yml` が毎週日曜にコメリ全店舗を再クロールし、GitHub Pages にデプロイします。

### 初回セットアップ

1. リポジトリを GitHub にプッシュ
2. GitHub リポジトリの **Settings → Pages** を開き、**Source** を「GitHub Actions」に設定
3. **Actions** タブ →「Update stores & deploy to Pages」→「Run workflow」で手動実行
4. 完了後、`https://<ユーザー名>.github.io/<リポジトリ名>/` で公開される

### スケジュールとオプション

- **定期実行**: 毎週日曜 04:17 UTC（日本時間 13:17）。`FRESH_DISCOVERY` モードでエリア再発見のみ行い、店舗詳細・座標はキャッシュ再利用して高速化。
- **手動実行（workflow_dispatch）**: Actions UI からいつでも実行可能。`full_refresh` オプションを ON にするとキャッシュを完全破棄して全件再取得（時間がかかります、新店舗の大量追加時などに）。
- **データ検証**: クロール結果が 1200店舗未満 or 座標カバレッジ 90%未満のとき（ブロック/部分失敗を疑う場合）はデプロイを中止します。

### キャッシュ

`crawl/crawl_cache.json` / `crawl/fill_cache.json` は `.gitignore` 対象（リポジトリに含めない）。代わりに `actions/cache` で実行間で永続化し、再実行を高速化します。

### デプロイされるファイル

`web/` の中身（`index.html` / `styles.css` / `app.js` / `data/`）が `site/` にコピーされて Pages にデプロイされます（相対パスで動作するため project pages でもOK）。