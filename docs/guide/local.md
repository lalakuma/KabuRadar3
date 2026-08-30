# KabuRadar3 ローカル運用ガイド

GitHub Actions の schedule は遅延することがあるため、**正確な時刻で動かすならローカル実行**を推奨します。

## 前提

```bat
cd c:\share\MorinoFolder\Python\KabuRadar3
set PYTHONPATH=src
pip install -r requirements.txt
rem data\kaburadar.db を手元の DB からコピー（初回のみ）
```

任意（Gemini / LINE）: プロジェクトルートに `.env` を作成（`.env.example` 参照）

## 手動実行（まず試す）

| やりたいこと | コマンド |
|--------------|----------|
| LO 本番相当（更新→解析→JSON） | `bat\screening_lo.bat` |
| HI 本番相当 | `bat\screening_hi.bat` |
| 解析だけ | `bat\analyze.bat --config config\config_lo.ini` |
| Web JSON だけ | `bat\publish.bat` |
| 解析→公開 JSON→git push | `bat\analyze_and_publish.bat` |
| 結果をブラウザ表示 | `bat\local_serve.bat` → http://127.0.0.1:8080/ |

## 自動実行（2つの方法）

### 方法 A: 常駐スケジューラ（おすすめ）

PC を起動したまま、30秒ごとに時刻を監視します。**9:00 / 10:00 / 16:00** の各ウィンドウ内で1回だけ実行します。

```bat
bat\run_local_scheduler.bat
```

- 実行済み記録: `data/local_schedule_state.json`
- スロット一覧: `python src/kaburadar3/scheduling/launcher.py --list`
- 本日の状態: `python src/kaburadar3/scheduling/launcher.py --status`

### 方法 B: Windows タスクスケジューラ（最も正確）

Actions と同様のずれがなく、**指定時刻ぴったり**に起動できます。

1. **タスクスケジューラ** を開く
2. 基本タスクを3つ作成（平日のみ・ログオン時でも可）

| タスク名 | トリガー | 操作 |
|----------|----------|------|
| KabuRadar3-HI-0900 | 平日 9:00 | `bat\screening_hi.bat` |
| KabuRadar3-LO-1000 | 平日 10:00 | `bat\screening_lo.bat` |
| KabuRadar3-LO-1600 | 平日 16:00 | `bat\screening_lo.bat` |

**プログラム:** `C:\share\MorinoFolder\Python\KabuRadar3\bat\screening_lo.bat`  
**開始:** `C:\share\MorinoFolder\Python\KabuRadar3\bat`

「ユーザーがログオンしているかどうかにかかわらず実行」+「最上位の特権で実行」は環境に応じて設定してください。

## ローカル vs GitHub Actions

| 項目 | ローカル | GitHub Actions |
|------|----------|----------------|
| 実行時刻の精度 | タスクスケジューラなら高い | schedule 遅延あり |
| PC 必要 | 実行時刻に PC 起動 | 不要 |
| DB | `data/kaburadar.db` 直読み（ローカル保持） | Actions cache（初回は手動シード要） |
| Gemini | `.env` の `GEMINI_API_KEY` | Secrets |
| Web 公開 | `publish.bat` で JSON 更新。push は任意 | gh-pages 自動 |

**v3 初期設定:** Actions の schedule は **OFF**（手動 Run workflow のみ）。ローカルを本番にしてください。

## トラブルシュート

| 症状 | 対処 |
|------|------|
| `ModuleNotFoundError` | `set PYTHONPATH=src` または bat 経由で実行 |
| DB なし | `data\kaburadar.db` を KabuRadar2 等からコピー |
| Gemini 評価なし | `.env` に `GEMINI_API_KEY`、runtime.json で `gemini_rating.enabled: true` |
| 同じスロットが再実行されない | `data/local_schedule_state.json` を確認。再実行したい日は該当 ID を削除 |
