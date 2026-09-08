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
- `price_per_unit`: 1枚あたりの単価 (USD)
- `total_amount`: 合計金額 (USD)。元の入力通貨・単価・合計・取引時為替は別列で保存
- `notes`: メモ

### 4. PortfolioSnapshots (資産推移記録)
毎日の資産額を記録
- `date`: 記録日
- `total_value_jpy`: その時点の総資産額 (円)

## セットアップ

1. 必要なパッケージのインストール:
```bash
pip install -r requirements.txt
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

ReferoのSteepスタイルから着想した、温かい白地と編集的な見出しのUIです。
ピーチ色はAI分析に限定し、主要操作は青、上昇は緑、下落は赤として金融上の
意味を保ちます。共有トークンを変更するときは、CSSとPythonの値を揃えてください。

## ライセンス

MIT License

## 2026-09 UI・ワークスペース更新

- 共通エントリーポイントで通貨・金額非表示をページ間で保持します。
- PCは比較表、狭幅では銘柄カード・下部ナビ。銘柄詳細は一覧から開くダイアログです。
- 大きな資産推移、価格影響額ランキング、数量目標・目標配分を追加しました。
- JPY取引・保存前確認・履歴複製・報酬テンプレートを追加。編集時は保存済み為替を保持します。
- 年初来損益は前年末時価と入出金評価が揃う場合のみ表示します。税務上の損益ではありません。
- USD未記録の履歴は、保存した当時のUSD/JPY日次レートから参考値を表示します。既存のUSD実測値を優先し、元の金額は変更しません。
- 目標と取引は管理者限定。金額マスクは画面表示機能であり公開情報のアクセス制御ではありません。
- `requirements.txt` は直接依存の固定版、`requirements.lock.txt` はテスト環境の全依存スナップショットです。

DBの追加変更は `supabase/migrations/20260905122319_portfolio_workspace.sql`。
接続中のCryptoプロジェクトでは20260905122638として適用済みです。再適用しないでください。

検証: `.venv/bin/python -m pytest -q`。画面テストには合成データとモックを使い、本番取引を登録しません。
iPhone実機Safari・実アカウントでの保存は別途確認対象です。

既存の公開専用ビューは列権限を限定したNOLOGIN所有者を利用しています。
Supabase Advisorの[Security Definer View指摘](https://supabase.com/docs/guides/database/database-linter?lint=0010_security_definer_view)は残りますが、所有者はsuperuserでもBYPASSRLSでもありません。
既存の[漏えいパスワード保護](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection)は無効のままで、今回のUI更新では認証設定を変更していません。

## 日次記録と過去の通貨表示

`snapshot_automation.sql` は、接続中のCryptoプロジェクトへ
`20260907235239_snapshot_currency_history_and_daily_recording` として適用済みです。
同じ追加DDLを再適用しないでください。

- Supabase Cronが日本時間の毎日9:05に実行します（UTCでは `5,20,35 0 * * *`）。
  9:20・9:35は未記録日の再試行枠です。アプリを開いておく必要はありません。
- CoinGeckoへの1回の取得でJPY/USDを同時に評価します。13銘柄など全保有分の
  有効な両通貨価格が揃わなければ例外とし、その日は保存しません。次の枠で再試行します。
- `portfolio_internal.capture_daily_snapshot()` は既存の日付を上書きしません。
  同時実行はロックと日付の一意制約で保護します。管理者の手動記録は同日分を更新できます。
- 自動処理は非公開スキーマ内の SECURITY INVOKER 関数で、所有者のCronだけが実行します。
  公開閲覧者・ログインユーザーへ書込権限やHTTP実行権限を追加していません。
- 初回の `portfolio_internal.backfill_snapshot_exchange_rates()` により、USD未記録の
  180日分へ [FrankfurterのECB日次為替](https://frankfurter.dev/) を付与しました。
  休業日は直前の公表値を採用し、公表日を保存します。元のJPY・USD金額は保持します。
  UIはUSD欠落時のみ `total_value_jpy / usd_jpy_rate` を参考値として表示します。
- 記録そのものが存在しない過去の日を補間することはありません。
  為替変動によりJPYとUSDで線の形が多少異なるのは正常です。

監視は `cron.job` の `cryptofolio-daily-snapshot` と `cron.job_run_details` を確認します。
停止するときは `cron.alter_job` の `active := false` を利用できます。
外部APIやSupabaseの停止中には保存されません。欠損価格を0として記録しません。

今回の検証は `python -m unittest discover -s tests -p test_history_currency.py`、
`python -m unittest discover -s tests -p test_snapshot_capture.py`、
および `tests/snapshot_automation_verify.sql`。
日次処理の実価格での初回保存、再実行時の重複防止、過去金額の保存前後一致も確認します。

## 分析メモの日次更新

- 旧モデル `gemini-2.0-flash` は[2026-06-01に提供終了](https://ai.google.dev/gemini-api/docs/deprecations)。
  画面刷新時に失われていた生成呼び出しを復元し、`gemini-2.5-flash` の
  [REST generateContent](https://ai.google.dev/api/generate-content) へ移行しました。
- 既存の Streamlit Secrets `[gemini].api_key` と `[supabase].secret_key` をそのまま使用します。
  GeminiキーをブラウザやDBにコピーしません。`[gemini].model` でモデルを変更できます。
  旧2.0モデルの設定だけは自動的に現行デフォルトへ移行します。
  利用可能なモデル一覧を1時間キャッシュして確認し、希望モデルがなければ対応中のFlash系モデルを選びます。
- その日最初に「市場データ・分析メモ」を開いたときに生成し、成功後は全閲覧者で共有します。
  **訪問のない日は生成しません。** 9:05の評価額自動記録とは別の処理です。
- 日付はJST。DBで生成権を取得し、同時閲覧・再読み込み・通貨切替による重複を防ぎます。
  失敗は15分後以降の閲覧時に再試行し、1日最大3回。中断した処理の生成権は10分後に失効します。
- 送信内容は公開保有銘柄の構成比、USD価格の24時間変化、寄与度、データ時刻のみです。
  数量・金額・取得原価・取引履歴・目標は送信しません。取得時刻が当日かつ15分以内の価格だけを使用します。
- 「全体の動き／変化の主因／確認ポイント」をJSONで生成・検証して保存します。
  過去のメモを当日の分析として表示せず、失敗時は状態と直接集計した事実を表示します。
  金額非表示時は生成せず、メモと過去の本文も隠します。
- `analysis_daily.sql` は既存の公開ビュー所有者・読み取り専用権限を維持します。
  2つのRPCは SECURITY INVOKER で、実行できるのはバックエンドのservice_roleのみです。
  `portfolio_internal.analysis_runs` の状態・試行回数・エラーコードで更新停止を確認できます。
- 検証：`python -m unittest discover -s tests -p test_daily_analysis.py` と
  `tests/analysis_daily_verify.sql`（当日未生成のときのみ。検証用の書き込みはロールバック）。
  公開画面でも生成・保存・再表示・通貨切替・金額非表示を確認します。
- Community Cloudで読み込み済みの古いモジュールが残る場合は再構築します。
  今回は依存マニフェストの更新で再構築し、生成結果まで確認します。
