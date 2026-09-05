# data/

SQLite データベース `kaburadar.db` を置くフォルダです。

## Git 管理について

**`kaburadar.db` は Git に含めません**（約 130MB のため）。各 PC でローカルに保持してください。

初回セットアップ:

1. 既存の `KabuRadar.db` / `KabuRadar2` の `data/kaburadar.db` を `data/kaburadar.db` にコピーする  
   または KabuRadar2 と同じ Google Drive / 共有フォルダ上の DB を `PATH_DB` で参照する
2. `config/config_lo.ini` の `PATH_DB = data/kaburadar.db` を確認

```bat
copy C:\path\to\KabuRadar.db data\kaburadar.db
```

## Git で管理するファイル

| ファイル | 内容 |
|----------|------|
| `special_state.json` | 特別買い状態 |
| `quality_cache.json` | Gemini 評価キャッシュ |
| `signal_ratings.jsonl` | 星評価の時系列履歴（publish 時に追記） |
| `local_schedule_state.json` | ローカルスケジューラ実行記録（通常は commit しない） |

## ★評価の方針（Gemini）

- **★3〜★4** が基本。★5 は稀。★1/★2 は構造悪材料など明確な理由があるときのみ。
- シグナルは RSI/RCI で既に抽出済みのため、yfinance の成長率だけで ★2 にしない。
- 詳細は `src/kaburadar3/qualitative/rater.py` のプロンプト（`PROMPT_VERSION`）を参照。

## バックアップ

DB は定期的に別ドライブやクラウドストレージへコピーすることを推奨します。
