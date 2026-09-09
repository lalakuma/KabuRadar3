# 変更履歴メモ

リファクタリング・整理の要点です（詳細は git log を参照）。

## 2026-08 日別タブを買いシグナル一覧に変更

- 買い（新買）があった日だけを日付順に表示し、銘柄をまとめて閲覧
- `daily.buy_days[]` を追加。返売り・日次損益は折りたたみ内

## 2026-08 Web に日別結果タブを追加

- `data.json` に `daily.days[]`（直近 60 営業日の日次損益・新買・返売り）
- Web **日別**タブ … 日付選択で過去のシグナルと損益を表示

## 2026-08 新買シグナル誤検出の修正

- `collect_today_signals` を **各銘柄 CSV の最終行のみ** 判定に変更（過去の新買を当日と誤認しない）
- 終値 `close <= 0` のシグナルを除外
- Actions cache を `v2` に更新し、DB サイズ 100MB 未満はエラー（LFS ポインタ／欠損 cache を拒否）

## 2026-08 DB をローカル専用に

- `data/kaburadar.db` を Git / LFS から除外（約 130MB）
- 本番 DB は各 PC で保持。clone 時は手元の DB をコピー

## 2026-08 LFS 上限・過剰実行の対策

- DB を **Actions cache** で実行間引き継ぎ（`kaburadar-db-v1`）。master への LFS push を廃止
- `Commit results` を `continue-on-error` に（JSON のみ commit）
- guard の 10:00 LO カバー開始を 12:30 → **10:05** に前倒し（schedule 遅延で重複 dispatch されていた）
- LINE 送信失敗をワークフロー失敗にしない

## 2026-07 1日3回（HI/LO 場中 + LO 引け後）

- **9:00 JST** … HI 場中（`config_hi.ini`）
- **10:00 JST** … LO 場中（`config_lo.ini`）
- **16:00 JST** … LO 引け後（`config_lo.ini`）
- guard のカバー時間帯を HI/LO で分離（前場 HI・午後場 LO）

## 2026-06 場中枠を 12:30 → 10:00 JST に前倒し

- schedule 遅延で 12:30 設定が 16 時台にずれていたため、場中 LO を **10:00** に変更（`0 1 * * 1-5` UTC）
- guard の場中スロットも 10:00 に合わせて更新

## 2026-06 本番スケジュールを LO 2回に整理

- 平日 **12:30 JST**（場中・午後場）と **16:00 JST**（引け後）の LO のみ
- 9:00 HI 検証枠と 15:00 枠を削除
- `schedule` 自動実行はすべて `config_lo.ini`

## 2026-06 9:00 schedule 遅延検証（一時・終了）

- HI 枠を 12:30 → **9:00 JST**（`0 0 * * 1-5` UTC）に変更
- `daily-screening` に `schedule verification` ログを追加
- guard の HI 補完を **17:00 まで待機**（`event: schedule` の実測を優先）
- 検証後は Actions の Started 時刻を確認し、12:30 に戻すか判断

## 2026-06 株価更新を過去5日分に変更

- `update_prices.py --menu 6` … 過去5日（yfinance `period=5d`）
- Actions `daily-screening` の株価更新を `--menu 1` から `--menu 6` に変更

## 2026-06 schedule 遅延対策（guard 強化）

- `daily-screening.yml` の `schedule`（12:30 / 15:00 / 16:00 JST）を復活
- `schedule-guard.yml` を強化（スロット直後 cron + 19:00 JST まで補完）
- guard の 90 分上限を撤廃し、12:30 HI が夕方までスキップされないよう修正
- `README.md` / `docs/guide/operations.md` / `docs/guide/cloud.md` の運用手順を更新

## 2026-06 当日シグナル・特別買い・Web タブ（フェーズ A）

- `config/runtime.json` … 広がり閾値・ETF・LINE トグル
- `signals/` … 今日の新買/返売り、特別買いステート（`data/special_state.json`）
- `data.json` に `today` / `special` / `runtime` / `controls`
- Web: タブ（今日・特別買い・損益・設定・実行リンク）
- LINE: 買い/返売り/特別買い通知
- Actions: `workflow_dispatch` で full / analyze / publish、lo / hi

## 2026-06 LINE 設定の v1 からの移植

- `scripts/sync_line_from_kaburadar.py` … v1 `line.py` → `.env` / GitHub Secrets
- `.env` を `.gitignore` に追加
- `notifications/line.py` がプロジェクトルートの `.env` を読むよう修正

## 2026-06 Web 実行表示・LINE 強化

- `data.json` にクラウド実行メタ（`run.pages_url` / `run.workflow_url`）を追加
- Web: 更新元（自動/手動）表示、実行ログへのリンク
- LINE: PF・勝率・Web URL・Actions ログ URL を含むサマリー
- `cloud.md` に Pages / LINE の初回セットアップ手順を追記

## 2026-05 12:30 は config_hi（RSI4反転）

- `config/config_hi.ini` 復活（`SCR_JDG_RSI4REV = 1`）
- 平日 **12:30 JST** → `config_hi.ini`、**15:00 / 16:00** → `config_lo.ini`
- 環境変数 `KABURADAR_CONFIG` で切替（`analyze.py --config` も可）
- Web 表示にモード（HI / LO）を表示

## 2026-05 スケジュール 1日3回

- Daily screening: 平日 **12:30・15:00・16:00 JST**（03:30 / 06:00 / 07:00 UTC）

## 2026-05 スケジュール 1日2回

- Daily screening: 平日 **15:00・16:00 JST**（06:00 / 07:00 UTC）

## 2026-05 クラウド専用運用

- 本番を GitHub Actions のみとする方針にドキュメントを統一
- Actions workflow に LINE 通知（Secrets 設定時）を追加
- ローカル bat / タスクスケジューラは本番では使わない旨を明記

## 2026-05 無料クラウド（GitHub Actions）

- `data/kaburadar.db` を Git LFS でリポジトリ管理可能に
- `.github/workflows/daily-screening.yml` … 平日 16:00 JST に解析 + push
- `docs/guide/cloud.md` を追加

## 2026-05 すぐ効く改善

- `publish --push` のブランチを `.env` / git 自動検出に変更
- 解析完了時に `enabled/written/skipped` をコンソール表示
- 取説に Windows 11 タスクスケジューラ手順、LINE 設定手順を追記
- `development.md` の拡張候補を現状に合わせて更新

## 2026-05 Linux 対応

- `sh/` ランチャー、`Makefile`、`docs/guide/linux.md`
- `config_lo.ini` のパスを `/` 表記に統一（Windows でも可）
- `scheduling/launcher` が OS に応じて bat / sh を選択
- CSV を **UTF-8 BOM**（`utf-8-sig`）に統一。読込は旧 cp932 もフォールバック

## 2026-05 個人運用向け

- LINE: `--notify` / `screening_notify.bat` / 集計 CSV から上位銘柄を送信
- `healthcheck.bat` … 設定・DB・CLI の確認
- 統合テスト: 最小 SQLite で `backtst_proc` を検証

## 2026-05 品質向上

- GitHub Actions **CI**（`pytest`）を追加
- `pipeline/analyze.run()` が失敗時に非ゼロ終了コードを返す（1=出力なし, 2=集計なし）
- `publish` が集計データ未変更時は `docs/data.json` を更新しない（無意味 commit 抑制）
- テスト追加（終了コード・RSI・publish 差分・パッケージ import）

## 2026-05 取扱説明書

- `docs/guide/manual.md` を追加（利用者向けの全体ガイド）

## 2026-05 機能ブロック構成

- `settings` / `domain` / `data` / `strategy` / `pipeline` / `market_data` / `publishing` / `scheduling` / `notifications` に分割
- `analysis/` は後方互換 import のみ（実装は上記パッケージへ移動）
- `legacy/`・`tasks/` ディレクトリ削除

## 2026-05 構成整理（前半）

- `legacy/` → 一時的に `analysis/`、`tasks/` → `cli/`
- `DB/` → `data/kaburadar.db`
- `output/honban/` → `output/results/`
- `config_hi.ini` 削除（LO / 短期 RSI 一本化）
- 未使用 `technical_*.py` 7 ファイル削除、RSI4 専用の `backtest_proc.py` に縮小
- bat を分かりやすい名前に整理（旧名は互換ラッパー）
- `docs/guide/` にプロジェクトドキュメントを追加

## 以前の改善（REFAC_SUMMARY より）

- 機密情報の `.env` 化
- 絶対パス依存の削減
- `requirements.txt` 整備
- GitHub Pages パイプライン（`publish` + Actions）
