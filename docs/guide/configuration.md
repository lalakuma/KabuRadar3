# 設定リファレンス

## 設定ファイル

| ファイル | 用途 | `SCR_JDG_RSI4REV` |
|----------|------|-------------------|
| [`config/config_lo.ini`](../../config/config_lo.ini) | 本番（10:00 場中 / 16:00 引け後 Actions） | `0` |
| [`config/config_hi.ini`](../../config/config_hi.ini) | 本番（9:00 場中 Actions） | `1` |

読み込み: `kaburadar.settings`（`config.py` は後方互換）。環境変数 `${...}` の展開あり。

クラウドでは Actions が `KABURADAR_CONFIG` で切り替えます。ローカルでは:

```bash
set KABURADAR_CONFIG=config\config_hi.ini
python src/kaburadar3/cli/analyze.py
# または
python src/kaburadar3/cli/analyze.py --config config/config_hi.ini
```

## [SCREENING] スクリーニング・バックテスト

| キー | 例 | 説明 |
|------|-----|------|
| `SCR_JDG_RSI4` | `1` | 短期 RSI 戦略を有効化（**本リポジトリは 1 固定運用**） |
| `SCR_JDG_RSI4REV` | `0` | RSI 反転パターンを使うか |
| `SCR_JDG_RSVENT` | `0` | 予約エントリー時の追加判定 |
| `SCR_SELLBUY` | `0` | 売買モード（`0` = 両建て切替） |
| `SCR_ENT_TIMING` | `0` | エントリータイミング（`0` 当日 / `1` 翌日） |
| `SCR_PAST_PERIOD` | `100` | 過去何日分を読むか（日数 × -1 で内部計算） |
| `SCR_SELL_PERIOD` | `100` | ポジション最大保有日数 |
| `SCR_RSI_*` / `SCR_SRSI_*` | — | RSI 閾値・期間 |
| `SCR_ENTRY_REST` | `0` | 決済後の再エントリー休止日数 |

削除済みの旧戦略（MACD・移動平均など）用 `SCR_JDG_*` キーは ini から除去済みです。

## [SHUUKEI] 出力パス

| キー | 既定値 | 説明 |
|------|--------|------|
| `PATH_HONBAN` | `output\results\` | 解析結果・集計 CSV の出力先 |
| `PATH_SHUUKEI` | `output\workspace\` | 作業用ディレクトリ |

## [DATABASE]

| キー | 既定値 | 説明 |
|------|--------|------|
| `PATH_DB` | `data\kaburadar.db` | SQLite ファイル（プロジェクトルート相対） |

## `config/runtime.json`（運用設定）

Web 表示・LINE 通知・特別買い（広がり）のしきい値。戦略パラメータは ini、運用トグルはこちら。

| キー | 既定 | 説明 |
|------|------|------|
| `special_buy.enabled` | `true` | 特別買いロジック |
| `special_buy.min_new_buy_count` | `7` | 当日「新買」がこの件数以上で特別買い |
| `special_buy.etf_default` | `1306` | 通知する ETF |
| `special_buy.exit_rsi` | `70` | 特別買い後の利確 RSI |
| `notify.today_buy` | `true` | LINE: 今日の買い |
| `notify.today_sellback` | `true` | LINE: 今日の返売り |
| `notify.special_buy_on` | `true` | LINE: 特別買い ON |
| `notify.special_exit` | `true` | LINE: 特別買い 売り |

編集: GitHub の [runtime.json を編集](https://github.com/lalakuma/KabuRadar3/edit/master/config/runtime.json) またはローカルで commit & push。

## 環境変数（.env）

`.env.example` 参照。

| 変数 | 用途 |
|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE 通知（Messaging API） |
| `LINE_USER_IDS` | 送信先ユーザー ID（カンマ区切り） |
| `KABURADAR_CONFIG` | 使用する ini（例: `config/config_hi.ini`） |
| `KABURADAR_GIT_BRANCH` | `publish --push` の push 先（未設定時は git が自動検出） |
| `KABUS_API_PASSWD` 等 | 将来の API 連携用（ini の `${...}` からも参照可） |

## 設定のコピー

解析実行時、使用中 ini のスナップショットが `output/results/` に保存されます（`copy_config_snapshot`）。

## CSV 文字コード

- **新規出力:** UTF-8 BOM（`utf-8-sig`）— Excel・Linux 両方で扱いやすい
- **読込:** 同形式を優先し、過去の cp932 ファイルも `settings.encoding.read_csv` で自動判定
