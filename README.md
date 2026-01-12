# 暗号資産ポートフォリオアプリ

暗号資産の保有状況を管理し、リアルタイム価格で資産価値を追跡するWebアプリケーションです。

## 機能

- 📊 **ポートフォリオ管理**: 保有する暗号資産の一覧表示と総資産額の計算
- 💰 **リアルタイム価格取得**: CoinGecko APIを使用した最新価格の取得
- 📈 **取引履歴管理**: 買い増し・売却の記録と損益計算
- 📉 **資産推移チャート**: 日次の資産額推移を可視化
- 🎨 **モダンなUI**: Streamlitによる直感的なインターフェース

## データベーススキーマ

### 1. Users (ユーザー)
将来的な拡張用のテーブル

### 2. Assets (通貨マスタ)
管理する暗号資産の情報
- `name`: 通貨名 (例: Bitcoin)
- `symbol`: シンボル (例: BTC)
- `api_id`: CoinGecko APIのID (例: bitcoin)
- `icon_url`: アイコン画像のURL

### 3. Transactions (取引履歴)
買い増しや売却の記録
- `date`: 取引日時
- `type`: 取引種類 ('Buy' or 'Sell')
- `asset_id`: 通貨ID (Assetsテーブルへの外部キー)
- `quantity`: 数量
- `price_per_unit`: 1枚あたりの購入単価 (円)
- `total_amount`: 合計支払額 (円)
- `notes`: メモ

### 4. PortfolioSnapshots (資産推移記録)
毎日の資産額を記録
- `date`: 記録日
- `total_value_jpy`: その時点の総資産額 (円)

## セットアップ

1. 必要なパッケージのインストール:
```bash
pip install streamlit requests pandas plotly
```

2. データベースの初期化:
```bash
python database.py
```

3. アプリケーションの起動:
```bash
streamlit run app.py
```

## 使用技術

- **Python 3.x**
- **Streamlit**: Webアプリケーションフレームワーク
- **SQLite**: データベース
- **CoinGecko API**: 暗号資産価格取得
- **Pandas**: データ分析
- **Plotly**: データ可視化

## ライセンス

MIT License
