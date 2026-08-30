# KabuRadar3

短期 RSI + **RCI V字反転** エントリー、**Gemini 銘柄評価（★1-5）** 付きのバックテスト・集計・GitHub Pages 公開。**本番は GitHub Actions（クラウド専用）**。

v3 初期運用: **ローカル実行を本番**（Actions schedule は OFF）。実行時刻の精度が必要な場合は [ローカル運用ガイド](docs/guide/local.md) を参照。

**運用:** [ローカル運用](docs/guide/local.md) · [クラウド運用ガイド](docs/guide/cloud.md) · [取扱説明書](docs/guide/manual.md)

## v3 の主な変更

- **エントリー:** RSI 売られすぎ **AND** RCI V字反転（`SCR_JDG_RCI=1`）
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
| **LINE** | [cloud.md](docs/guide/cloud.md) の Secrets 設定後、自動通知 |

手動実行: GitHub **Actions** → **Daily screening (cloud)** → **Run workflow**
（自動監視は **Daily screening schedule guard**）

## ディレクトリ構成

```
KabuRadar3/
├── .github/workflows/   # CI + 本番 daily-screening + schedule-guard
├── config/config_lo.ini # LO 戦略（SCR_JDG_RSI4REV=0）
├── config/config_hi.ini # HI 戦略（SCR_JDG_RSI4REV=1・9:00 場中用）
├── data/kaburadar.db    # SQLite（Git LFS）
├── docs/                # GitHub Pages + data.json
└── src/kaburadar3/       # Python 本体
```

`bat/` / `sh/` は **開発・デバッグ用**（本番では使わない）。

## 初回セットアップ

1. リポジトリを clone（`git lfs pull`）
2. Actions で **Daily screening (cloud)** を手動実行
3. 成功したら Pages を確認

詳細: [docs/guide/cloud.md](docs/guide/cloud.md)

## ローカル本番（推奨）

```bat
set PYTHONPATH=src
pip install -r requirements.txt

rem 手動1回（LO）
bat\screening_lo.bat

rem 自動（9:00 / 10:00 / 16:00 を監視）
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
