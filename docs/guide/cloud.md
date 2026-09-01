# 無料クラウド実行（GitHub Actions）— 補助運用

**KabuRadar3 の本番はローカル実行**です。Actions は手動 workflow による **Web 公開の補助** として使えます。

**DB（`data/kaburadar.db`）は Git / LFS に含めません。** クラウド実行時は **Actions cache** に DB が残っている場合のみ動作します（初回はローカルで解析して cache を温めるか、ローカル本番を使ってください）。

**条件: 無料** — 公開リポジトリなら Actions / Pages の無料枠内で運用可能です。

## 仕組み

```
手動 Run workflow
  → GitHub Actions (Ubuntu)
  → Actions cache から data/kaburadar.db を復元（なければ失敗）
  → yfinance で過去5日分を取得 → SQLite に書込
  → 全銘柄バックテスト → 集計
  → docs/data.json 生成
  → gh-pages へデプロイ（Web 更新）
  → special_state.json / docs/data.json を master に commit（任意・失敗しても続行）
```

**PC は不要**（Web だけ見る場合）。DB 更新・正確な時刻実行は [local.md](local.md) を参照。

## 日常の運用

| やること | 頻度 |
|----------|------|
| **Web で結果を見る** | 毎日 · https://lalakuma.github.io/KabuRadar3/ （**今日**タブに買い/返売り） |
| **手動実行** | Actions → Run workflow（`job`: full / analyze / publish） |
| **運用設定** | [runtime.json を編集](https://github.com/lalakuma/KabuRadar3/edit/master/config/runtime.json) |
| **LINE でサマリー** | **ローカルのみ**（`.env`）。クラウドからは送らない |
| Actions 成功確認 | 初回のみ / 障害時 |
| 手動再実行 | 必要時 → Actions → Run workflow |
| ローカル screening | **しない** |

### Web で見られる内容

- 全体 PF・勝率・損益合計・銘柄一覧（検索・並び替え）
- **今日**タブ … 最新営業日の新買・返売り
- **日別**タブ … 買いシグナルがあった日と銘柄を一覧表示（直近 60 営業日）。返売り・損益は折りたたみ内
- **特別買い**タブ … 広がり ETF 状態
- 更新日時・モード（HI / LO）
- クラウド実行時は **「今回の実行ログ」** リンク（GitHub Actions の run へ）

## 初回セットアップ（Web + LINE）

### 1. GitHub Pages

1. リポジトリ **Settings** → **Pages**
2. **Build and deployment** → Source: **Deploy from a branch**
3. Branch: **`gh-pages`** / **`/ (root)`** → Save  
   （Actions が `daily-screening` 完了時に `gh-pages` へデプロイします）

### 2. 動作確認

1. **Actions** → **Daily screening (cloud)** → **Run workflow**
2. 成功（緑）まで待つ（10〜30 分程度）
3. https://lalakuma.github.io/KabuRadar3/ を開き、更新日時が変わっているか確認

DB はリポジトリに含まれません。ローカルで `bat\screening_*.bat` を実行し、`publish.bat` で Web を更新するのが v3 の標準運用です。

## スケジュール

| 項目 | 値 |
|------|-----|
| 本体ワークフロー | `.github/workflows/daily-screening.yml`（**手動のみ**） |
| 監視ワークフロー | `.github/workflows/schedule-guard.yml`（**OFF**） |
| 本番実行 | ローカル **11:30 / 15:00 / 16:00 LO**（[local.md](local.md)） |
| 手動 | Actions → Run workflow（Web 更新用・LINE なし） |

## 設定変更

1. `config/config_lo.ini` を編集
2. commit & push
3. 次回 Actions 実行から反映

## LINE 通知（任意）

### Secrets の登録

| Secret | 用途 |
|--------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API |
| `LINE_USER_IDS` | 送信先（カンマ区切り） |
| `GEMINI_API_KEY` | シグナル銘柄の ★1-5 評価（任意） |

Gemini は [Google AI Studio](https://aistudio.google.com/apikey) で API キーを発行し、**Settings → Secrets → Actions** に `GEMINI_API_KEY` として登録します。未設定時は解析・Web 公開は動作し、AI 評価のみスキップされます。

### LINE Secrets（従来）

**既存 KabuRadar (v1) を使っている場合** — `software/src/line.py` と同じトークン・ユーザー ID を移植できます:

```bash
python scripts/sync_line_from_kaburadar.py --env --gh-secrets
```

（`--env` はローカル `.env`、`--gh-secrets` は GitHub Actions 用。v1 を clone 済みか `--line-py` でパス指定）

手動で入れる場合: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | 内容 |
|--------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | [LINE Developers](https://developers.line.biz/) → Messaging API チャネル → チャネルアクセストークン（長期） |
| `LINE_USER_IDS` | 自分のユーザー ID（`U` で始まる）。複数は **カンマ区切り** |

ユーザー ID の調べ方: チャネルに友だち追加 → Webhook または公式手順で確認。

### 送信される内容（例）

```
KabuRadar LO（RSI4反転なし）
2026-06-01 20:08 JST
PF 2.993 · 勝率 78.1% (57勝16敗) · 損益 +319,100
— 損益上位 —
9024 西武ホールディングス ¥44,000 (W1L0)
…
Web: https://lalakuma.github.io/KabuRadar3/
Log: https://github.com/lalakuma/KabuRadar3/actions/runs/…
```

- 平日のみ送信（土日はスキップ）
- Secrets 未設定のときは Actions ログに `LINE secrets not set, skipping.` のみ（解析は続行）

## 無料枠の目安

| サービス | 公開 repo |
|----------|-----------|
| GitHub Actions | 手動実行のみ（schedule OFF） |
| GitHub Pages | 無料 |

**DB:** Git / LFS 非管理。Actions では **cache**（`kaburadar-db-v3`）のみ利用。

## ローカル clone する人へ

結果をローカルで見る必要はありません。コード編集時のみ:

```bash
git clone <url>
cd KabuRadar3
copy C:\path\to\KabuRadar.db data\kaburadar.db
```

**`bat\screening.bat` は実行しないでください**（DB が競合します）。

## トラブルシュート

| 症状 | 対処 |
|------|------|
| Actions 失敗（赤） | ログ確認。DB cache 未シードの場合は [local.md](local.md) でローカル実行 |
| DB なし | DB は Git 管理外。ローカルに `data/kaburadar.db` を配置 |
| サイト古い | Actions 成功後も Pages 未デプロイだった → **修正済**（screening 末尾で gh-pages へデプロイ） |
| Pages が `errored` | Settings → Pages で branch **`gh-pages`** を指定。Actions を再実行 |
| LINE が来ない | Secrets 名の綴り・友だち追加・平日か確認。429（送信過多）のときは翌日まで待つか、guard による重複実行が収まるのを待つ |
| ローカルと結果が違う | ローカル screening を止める |

## GitHub Pages が更新されない理由

Actions bot が `master` へ push しても、**別 workflow は自動起動しない** GitHub の仕様があります。  
`daily-screening` の末尾で **gh-pages へ直接デプロイ**するよう修正済みです。

## 関連

- [operations.md](operations.md) — 運用概要
- [configuration.md](configuration.md) — ini 項目
- [setup.md](setup.md) — 初回セットアップ
