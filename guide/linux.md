# Linux / macOS での運用

Python 本体は Windows と同じです。ランチャーだけ `bat/` の代わりに **`sh/`** または **Makefile** を使います。

## 前提

- Python 3.10 以上
- `bash`
- 仮想環境推奨: `python3 -m venv .venv && source .venv/bin/activate`
- 依存: `pip install -r requirements.txt`

## 初回セットアップ

```bash
git clone <repository-url>
cd KabuRadar3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdir -p data output/results
# 元 DB を data/kaburadar.db にコピー

export PYTHONPATH=src   # シェルスクリプトは自動設定しますが、手動実行時は必要
pytest -q
bash sh/healthcheck.sh
```

`.env` は任意（LINE 通知時）。`cp .env.example .env` で作成。

## 日常コマンド（sh）

| 目的 | コマンド |
|------|----------|
| 株価更新 + 解析 | `bash sh/screening.sh` |
| 解析のみ | `bash sh/analyze.sh` |
| 株価更新のみ | `bash sh/update_prices.sh --menu 1` |
| Web 用 JSON | `bash sh/publish.sh` |
| JSON + git push | `bash sh/publish.sh --push` |
| 解析 + 公開 | `bash sh/analyze_and_publish.sh` |
| 解析 + LINE | `bash sh/screening_notify.sh` |
| 環境チェック | `bash sh/healthcheck.sh` |
| スケジューラ | `bash sh/run_scheduler.sh` |

実行権限を付ける場合（任意）:

```bash
chmod +x sh/*.sh
./sh/screening.sh
```

## Makefile（任意）

```bash
make test
make health
make screening
make publish
make analyze-publish
```

## cron の例

平日 15:30 に株価更新:

```cron
30 15 * * 1-5 cd /path/to/KabuRadar3 && /path/to/.venv/bin/bash sh/update_prices.sh --menu 1 >> output/logs/cron.log 2>&1
```

解析 + 公開（時間は環境に合わせて調整）:

```cron
0 16 * * 1-5 cd /path/to/KabuRadar3 && bash sh/screening.sh && bash sh/publish.sh --push
```

## Windows との違い

| 項目 | Windows | Linux |
|------|---------|-------|
| ランチャー | `bat\*.bat` | `sh/*.sh` |
| 設定パス | `config_lo.ini` は `/` でも可 | 同左 |
| CSV 文字コード | UTF-8 BOM | UTF-8 BOM（旧 cp932 ファイルは読込時に自動判定） |
| スケジューラ | タスクスケジューラ + `run_scheduler.bat` | cron + `run_scheduler.sh` |

スケジューラ本体（`scheduling/launcher.py`）は OS に応じて `bat/` または `sh/` を自動選択します。

## トラブルシュート

| 症状 | 対処 |
|------|------|
| `ModuleNotFoundError: kaburadar` | `export PYTHONPATH=src` または `sh/` 経由で実行 |
| `bad interpreter` | `bash sh/xxx.sh` で実行（CRLF の場合は `git config core.autocrlf input`） |
| DB なし | `data/kaburadar.db` を配置 |
| CSV 文字化け | 新規出力は UTF-8 BOM。古い cp932 CSV はそのまま読める |

詳細は [取扱説明書](manual.md)・[セットアップ](setup.md) を参照。
