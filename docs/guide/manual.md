# KabuRadar3 取扱説明書

本書は **KabuRadar3** の使い方を、初めて触る人でも迷わないようにまとめた取扱説明書です。  
技術的な内部構成は [アーキテクチャ](architecture.md) を、設定項目の一覧は [設定リファレンス](configuration.md) を参照してください。

---

## 1. このツールは何をするか

KabuRadar3 は、登録銘柄について **短期 RSI 戦略** のバックテストを行い、結果を集計して **スマホやブラウザから見られる Web ページ**（GitHub Pages）に載せるためのツールです。

| できること | 説明 |
|------------|------|
| 株価の更新 | Yahoo Finance 経由で DB 内の日足を更新 |
| 全銘柄解析 | 有効銘柄ごとにバックテストし CSV・Excel を出力 |
| Web 公開 | 集計結果を JSON にし GitHub Pages で表示 |
| LINE 通知 | 集計後の損益上位銘柄を送信（`.env` 設定時・任意） |

**できないこと（現状）**

- 証券会社への自動発注（Kabuステーション連携は本リポジトリの範囲外）

---

## 2. 必要なもの

| 項目 | 内容 |
|------|------|
| **本番** | **GitHub Actions のみ**（PC・Python 不要） |
| GitHub アカウント | リポジトリ + Actions + Pages |
| データベース | `data/kaburadar.db`（**ローカルのみ**・Git 管理外） |
| ネットワーク | Actions 側で株価取得・push |

ローカル Python は **コードを直すときだけ**必要です。

初回: [cloud.md](cloud.md) · [セットアップ](setup.md)

---

## 3. フォルダの見方（最低限覚える場所）

```
KabuRadar3/
├── .github/workflows/  ← 本番（Daily screening）
├── config/config_lo.ini
├── data/kaburadar.db   ← ローカル SQLite（Git 管理外）
└── docs/data.json      ← Web 表示用
```

**本番で触るもの**

- GitHub **Actions** … 実行・ログ確認
- `config/config_lo.ini` … 設定変更（git push）
- https://lalakuma.github.io/KabuRadar3/ … 結果閲覧

**本番では使わない**

- `bat\screening.bat` 等 … DB 競合のため
- タスクスケジューラ … Actions が代替

---

## 4. 初回セットアップ（ローカル本番）

1. リポジトリを clone
2. `data/kaburadar.db` を手元の DB からコピー（[data/README.md](../../data/README.md)）
3. `bat\screening_lo.bat` で動作確認
4. 自動実行は `bat\run_local_scheduler.bat` または Windows タスクスケジューラ

Web 公開のみ Actions を使う場合: [cloud.md](cloud.md)

---

## 5. 日常の使い方（クラウド）

### 5.1 平日

**何もしなくて OK。** 平日 **9:00（HI・場中）・10:00（LO・場中）・16:00（LO・引け後）JST** に Actions が自動実行します。

結果: https://lalakuma.github.io/KabuRadar3/

### 5.2 手動で今すぐ実行

GitHub → **Actions** → **Daily screening (cloud)** → **Run workflow**

### 5.3 設定を変えたい

`config/config_lo.ini` を編集 → commit & push → 次回 Actions から反映

### 5.4 LINE（任意）

GitHub **Secrets** に `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_IDS` を設定（[cloud.md](cloud.md)）

---

## 5b. ローカル bat（開発・緊急時のみ・本番では使わない）

| やりたいこと | コマンド |
|--------------|----------|
| 株価更新 + 解析 | `bat\screening.bat` **← 本番では禁止** |
| 解析だけ（株価は更新しない） | `bat\analyze.bat` |
| 株価だけ更新 | `bat\update_prices.bat` |
| Web 用 JSON を作る | `bat\publish.bat` |
| JSON を作って GitHub に公開 | `bat\publish.bat --push` |
| 解析から公開まで一気に | `bat\analyze_and_publish.bat` |
| 更新・解析・LINE サマリー | `bat\screening_notify.bat` |
| 設定・DB の確認 | `bat\healthcheck.bat` |

いずれも **プロジェクトのルート** で実行するか、bat をダブルクリックしてください（内部で `PYTHONPATH` を設定します）。

### 5.2 平日の典型フロー（推奨）

**パターン A: 解析してからスマホで見る**

```bat
bat\screening.bat
bat\publish.bat --push
```

1〜2 分後にブラウザで開く:  
https://lalakuma.github.io/KabuRadar3/

**パターン B: すでに解析済みで Web だけ更新**

```bat
bat\publish.bat --push
```

**パターン C: まとめて実行**

```bat
bat\analyze_and_publish.bat
```

**パターン D: LINE に損益上位を通知（.env 設定済み）**

```bat
bat\screening_notify.bat
```

週末は送信しません。未設定のときはスキップして解析は続行します。

`--push` を付けると `docs/data.json` が commit され `origin/master` へ push されます。  
**パスワード入力なしで push できる**（SSH 鍵または Credential Manager）ことが前提です。

### 5.3 株価更新の期間を選ぶ

`update_prices.bat` または `screening.bat` 内の更新では、メニューで期間を選べます。

| 番号 | 期間 |
|------|------|
| 1 | 1 日 |
| 2 | 10 日 |
| 3 | 30 日 |
| 4 | 100 日 |
| 5 | 5 年 |
| 6 | 5 日（Actions 本番で使用） |

CLI から番号指定する例:

```bat
set PYTHONPATH=src
python src\kaburadar\cli\update_prices.py --menu 3
```

### 5.4 解析にオプションを付ける

```bat
set PYTHONPATH=src
python src\kaburadar\cli\analyze.py --publish
```

`--publish` は解析成功後に `publish.py --push` を続けて実行します。

---

## 6. 結果の読み方

### 6.1 出力ファイル（`output/results/`）

| 種類 | ファイル名の例 | 意味 |
|------|----------------|------|
| 銘柄別 CSV | `code7203_rsi_..._PF....csv` | 1 銘柄のバックテスト明細 |
| 集計 CSV | `Y0_PF1.2_W10L3_rate79.17_all12345.csv` | 全銘柄サマリー（Web 公開の元） |
| Excel | `集計_LO.xlsx` | トレード履歴・銘柄一覧シート |
| 設定コピー | `config_lo.ini` | 解析時点の設定スナップショット |

集計 CSV のファイル名には、おおよそ次の情報が含まれます。

- `PF` … プロフィットファクター（利益合計 ÷ 損失合計の目安）
- `W` / `L` … 勝ち・負け件数
- `rate` … 勝率（%）
- `all` … 損益合計（円ベースの集計値）

### 6.2 GitHub Pages（スマホ表示）

`publish` が `docs/data.json` を生成します。サイトには次が表示されます。

- **今日** … 最新営業日の新買・返売り
- **日別** … 買いシグナルがあった日と銘柄を一覧（返売り・損益は折りたたみ）
- **特別買い** … 広がり ETF 状態
- **損益一覧** … 全体サマリー・銘柄ランキング

**注意:** `publish` は `output/results/` に **最新の `Y*_PF*.csv`** がないと失敗します。先に `analyze` または `screening` を完走させてください。

### 6.3 ログ

| ファイル | 内容 |
|----------|------|
| `output/logs/debug.log` | 解析・スケジューラの記録 |

エラー時はこのファイルの末尾を確認してください。

---

## 7. 設定の変更（ユーザー向け）

設定ファイル: `config/config_lo.ini`  
変更後は **次回の解析から** 反映されます。

### よく触る項目

| セクション | キー | 意味（ざっくり） |
|----------|------|------------------|
| SCREENING | `SCR_PAST_PERIOD` | 過去何日分のデータで試すか |
| SCREENING | `SCR_SELL_PERIOD` | 何日保有したら決済するか |
| SCREENING | `SCR_SRSI_HI` / `SCR_SRSI_LOW` | RSI の利確・エントリー付近の閾値 |
| SHUUKEI | `PATH_HONBAN` | 結果 CSV の出力先（既定 `output\results\`） |
| DATABASE | `PATH_DB` | DB ファイルの場所 |

本リポジトリは **短期 RSI（`SCR_JDG_RSI4 = 1`）専用** です。MACD など旧戦略用のキーはありません。

全項目: [設定リファレンス](configuration.md)

---

## 8. 自動実行（スケジューラ）

`bat\run_scheduler.bat` を **タスクスケジューラ** で定期実行すると、時刻に応じて bat が起動します。

| 時刻帯（目安） | 実行内容 |
|----------------|----------|
| 9:00〜14:30 | `screening.bat`（更新＋解析） |
| 11:30〜12:00 | 同上 |
| 15:00〜15:30 | `update_prices.bat`（株価更新のみ） |

時刻の変更: `src/kaburadar3/scheduling/launcher.py` を編集。

### Windows 11: タスクスケジューラ登録例

1. **タスクスケジューラ** を開く → **タスクの作成**
2. **全般**
   - 名前: `KabuRadar3 scheduler`
   - 「ユーザーがログオンしているときのみ実行」でも可
3. **トリガー** → **新規**
   - 毎日、繰り返し間隔 **10 分**、継続時間 **10 時間**（9:00 開始など）
4. **操作** → **新規**
   - 操作: プログラムの開始
   - プログラム/スクリプト:

     ```
     C:\share\MorinoFolder\Python\KabuRadar3\bat\run_scheduler.bat
     ```

   - **開始**（作業フォルダ）:

     ```
     C:\share\MorinoFolder\Python\KabuRadar3\bat
     ```

5. **条件**タブで「コンピューターを AC 電源で使用している場合のみ」をオフ（ノート PC 向け）
6. 保存後、右クリック → **実行** で一度テスト。`output\logs\debug.log` に `Launcher started` が出れば OK

**Linux:** cron で `bash /path/to/KabuRadar3/sh/run_scheduler.sh`（[linux.md](linux.md) 参照）。

---

## 9. 旧 bat 名について

以前のファイル名でも同じ処理が動きます（中身は新しい bat を呼ぶだけ）。

| 旧名 | 新名 |
|------|------|
| `2-2.KabuStation_kessai_GetYahooF.bat` | `screening.bat` |
| `2-3.GetKabuka_GetYahooF.bat` | `update_prices.bat` |
| `1.kabu_main.bat` | `run_scheduler.bat` |
| `publish_results.bat` | `publish.bat` |

---

## 10. トラブルシューティング

| 症状 | 対処 |
|------|------|
| `DBが見つかりません` | `data/kaburadar.db` があるか、`PATH_DB` が正しいか確認 |
| `集計 CSV が見つかりません` | `bat\analyze.bat` または `screening.bat` が最後まで終わったか確認 |
| `price over` と表示されて銘柄が飛ぶ | 終値が上限（約 4000 円超）の銘柄はスキップする仕様 |
| `git push` が失敗 | リモートの先行コミットを pull、認証（SSH / PAT）を確認 |
| push したのにサイトが変わらない | GitHub Actions の完了を 1〜2 分待つ。Pages の branch が `gh-pages` か確認 |
| 解析が途中で止まった | `debug.log` を確認。DB 破損や銘柄テーブル欠損の可能性 |
| `analyze` の終了コード 1 | 有効銘柄はあるが CSV が 1 件も出なかった |
| `analyze` の終了コード 2 | 銘柄 CSV はあるが集計 `Y*_PF*.csv` ができていない |
| `publish` しても commit されない | 集計データが前回と同じ（`generated_at` だけの差分は commit しない） |
| pytest が失敗 | `set PYTHONPATH=src` のうえで `pip install -r requirements.txt` |

### 安全のための注意

- **本番用 DB** を `PATH_DB` に指定している場合、集計処理は `TradeHist` テーブルを作り直します。テスト用 DB を使うか、必ずバックアップを取ってください。
- `publish --push` は **リモートの master に commit します**。他人と共有するリポジトリでは push 前に diff を確認してください。

---

## 11. 用語集

| 用語 | 説明 |
|------|------|
| 短期 RSI | 4 日程度の RSI を使った売買シグナル（TradingView 式） |
| バックテスト | 過去の日足で「買い・売り」をシミュレーションすること |
| screening | 本ツールでは「株価更新 → 全銘柄解析」の一連処理 |
| PF | Profit Factor。利益の大きさと損失の大きさの比率の目安 |
| GitHub Pages | GitHub がホストする静的 Web サイト（本プロジェクトの結果表示用） |

---

## 12. 関連ドキュメント

| ドキュメント | 向け |
|--------------|------|
| [セットアップ](setup.md) | 初回構築 |
| [日常運用](operations.md) | bat・CLI の一覧 |
| [設定リファレンス](configuration.md) | ini の全キー |
| [アーキテクチャ](architecture.md) | ソース構成・処理フロー |
| [開発・テスト](development.md) | 改修・pytest |
| [変更履歴メモ](changelog.md) | 整理の経緯 |

---

## 13. 改訂履歴（本書）

| 日付 | 内容 |
|------|------|
| 2026-05-30 | 機能ブロック構成後の初版取扱説明書 |
