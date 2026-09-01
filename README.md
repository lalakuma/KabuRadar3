# KabuRadar3

短期 RSI + **RCI V字反転** エントリー、**Gemini 銘柄評価（★1-5）** 付きのバックテスト・集計・GitHub Pages 公開。

**本番はローカル実行**（Actions schedule は OFF）。DB（約 130MB）も **ローカル保持**（Git / LFS 非管理）。

**運用:** [ローカル運用](docs/guide/local.md) · [クラウド運用ガイド](docs/guide/cloud.md) · [取扱説明書](docs/guide/manual.md)

## v3 の主な変更

- **エントリー:** RSI 売られすぎで準備 ON → 30営業日以内に RCI 上向きで確定（RSI 回復では準備 OFF にしない）
- **決済:** RSI4 が `SCR_SRSI_HI`（60）超で返売り。`-3%` 損切り（`SCR_JDG_STOP_LOSS`）
- **Gemini 評価:** 当日シグナル銘柄を ★1-5 で分類（`GEMINI_API_KEY` 設定時）
- **パッケージ:** `src/kaburadar3/`

## 本番の流れ（PC 不要）

```
手動 Run workflow（初期）
  → 株価更新 → 解析（RSI+RCI）→ Gemini 評価 → Web 公開
```

| 確認 | URL |
|------|-----|
| **解析結果（Web）** | https://lalakuma.github.io/KabuRadar3/ |
| **実行ログ** | [Actions · Daily screening](https://github.com/lalakuma/KabuRadar3/actions/workflows/daily-screening.yml) |
| **LINE** | ローカル実行時のみ（`.env` 設定時） |

手動実行: GitHub **Actions** → **Daily screening (cloud)** → **Run workflow**
（クラウド自動実行・guard は **OFF**。手動 Run workflow のみ）

## ディレクトリ構成

```
KabuRadar3/
├── .github/workflows/   # CI + 本番 daily-screening + schedule-guard
├── config/config_lo.ini # 本番 LO 戦略（RSI prep → RCI 上向き）
├── config/config_hi.ini # 旧 HI（非推奨・比較用に残置）
├── data/kaburadar.db    # SQLite（ローカルのみ・Git 管理外）
├── docs/                # GitHub Pages + data.json
└── src/kaburadar3/       # Python 本体
```

`bat/` / `sh/` は **開発・デバッグ用**（本番では使わない）。

## 初回セットアップ

1. リポジトリを clone
2. `data/kaburadar.db` を手元の DB からコピー（[data/README.md](data/README.md)）
3. `.env` を作成（Gemini / LINE を使う場合）
4. 下記「ローカル本番」で動作確認

## ローカル本番

```bat
set PYTHONPATH=src
pip install -r requirements.txt

rem 手動1回（LO）
bat\screening_lo.bat

rem 自動（平日 11:30 / 15:00 / 16:00 LO — Windows タスクまたは常駐）
bat\register_task_scheduler.bat
bat\run_local_scheduler.bat

rem 結果確認
bat\local_serve.bat
```

詳細: [docs/guide/local.md](docs/guide/local.md)

## 開発（ローカル）

```bat
set PYTHONPATH=src
pip install -r requirements.txt
pytest
```

本番の `screening.bat` は **実行しない**（DB 競合防止）。

## 公開 URL

https://lalakuma.github.io/KabuRadar3/
