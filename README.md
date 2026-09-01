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

### スナップショット保存用Secrets

管理者ログイン中は、追加の管理コード入力なしでスナップショットを保存できます。
未ログイン時のスナップショット追加は、Streamlitのサーバー側Secretsに保存した管理コードで保護します。
既存の `[supabase]` セクションへ `secret_key` を追加し、`[snapshot_admin]` セクションを作成してください。

```toml
[supabase]
url = "https://PROJECT_REF.supabase.co"
key = "公開表示用のpublishableまたはanonキー"
secret_key = "バックエンド専用のsb_secretキー"

[snapshot_admin]
pin = "12文字以上の管理コード"
```

`secret_key` と `pin` はGit・チャット・ブラウザへ出さず、StreamlitのSecrets設定内だけに保存します。
Supabaseでは、このアプリ専用の名前付きSecret keyを作成して使用してください。

### 管理者ログインと取引管理

公開ページは匿名のまま閲覧できますが、取引・資産マスタの追加、編集、削除には
Supabase Authのメールアドレス／パスワードと管理者許可リストが必要です。

1. `security_phase2_admin_auth.sql` をSupabaseへ適用します。
2. Supabase DashboardのAuthenticationで管理者ユーザーを1名作成します。
3. 作成したユーザーのUUIDを `public.portfolio_admins.user_id` に登録します。
4. アプリのサイドバーにある「管理者ログイン」からログインします。

パスワード、JWT、Secret keyはGit・チャット・SQLファイルへ記載しないでください。
`security_phase2_admin_auth.sql` の適用後は、旧
`security_phase1_lockdown_anon.sql` を重ねて実行しないでください。

### CoinGeckoのレート制限対策

現在価格は全ページ・全ユーザーで10分間共有し、429応答後は60秒間API呼び出しを停止します。
Demo APIキーは任意です。利用する場合のみ、Streamlit Secretsへ次を追加してください。

```toml
[coingecko]
api_key = "CoinGecko Demo APIキー"
```

このキーもGitやチャットへ貼らず、StreamlitのSecrets設定内だけに保存してください。

## 使用技術

- **Python 3.x**
- **Streamlit**: Webアプリケーションフレームワーク
- **Supabase**: データベース
- **CoinGecko API**: 暗号資産価格取得
- **Pandas**: データ分析
- **Plotly**: データ可視化

## デザインシステム

UIを変更する前に [`DESIGN.md`](DESIGN.md) を参照してください。

- ブラウザ向けトークン: `styles/main.css`
- Plotly／Python向けトークン: `components/design_tokens.py`
- Codex向けの参照ルール: `AGENTS.md`

Apple風の落ち着いたダークUIを基調とし、色は主要操作と金融上の意味、
暗号資産データの識別に限定して使用します。共有トークンを変更するときは、
CSSとPythonの値を揃えてください。

## ライセンス

MIT License
