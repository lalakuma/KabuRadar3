# 日常運用（クラウド専用）

**本番運用は GitHub Actions のみ**です。PC 上の `bat` / タスクスケジューラは使いません。

詳細: **[cloud.md](cloud.md)**

## あなたがすること

| 頻度 | 操作 |
|------|------|
| **初回** | Actions で **Daily screening (cloud)** を Run workflow |
| **平日** | 何もしない（**9:00 HI / 10:00 LO / 16:00 LO** JST 目標で自動実行） |
| **確認** | https://lalakuma.github.io/KabuRadar3/ |
| **設定変更** | `config/config_lo.ini` を編集 → commit & push |

## 自動処理の内容（Actions）

```
株価更新 (yfinance・過去5日)
  → 全銘柄バックテスト
  → docs/data.json 生成
  → docs/data.json 生成 → gh-pages デプロイ
  → special_state.json / docs/data.json を master に commit（DB は Actions cache）
  → GitHub Pages 更新
```

## 手動実行（急ぎのとき）

GitHub → **Actions** → **Daily screening (cloud)** → **Run workflow**

## 実行時刻の安定化（二重起動）

- **本体** `Daily screening (cloud)` … 平日 **9:00（HI・場中）** / **10:00（LO・場中）** / **16:00（LO・引け後）** JST。
- **監視** `Daily screening schedule guard` … 各スロット直後と 5 分間隔で未実行をチェックし、19:00 まで補完。
- schedule 遅延の目安: 9:00 設定 → 11 時台、10:00 設定 → 14 時台、16:00 設定 → 19 時台。

## ローカルでやらないこと

| やらない | 理由 |
|----------|------|
| `bat\screening.bat` | DB が Actions の push と競合する |
| `run_scheduler.bat` / タスクスケジューラ | クラウド側でスケジュール済み |
| `publish.bat --push` | Actions が JSON も push する |

ローカルに **Python 環境は不要**（コード編集・`pytest` だけする場合は除く）。

## ローカルを止めるチェックリスト

- [ ] タスクスケジューラの `KabuRadar3` タスクを **無効化または削除**
- [ ] 平日の `screening.bat` 実行を止める
- [ ] GitHub **Actions** が緑（成功）になることを一度確認

## LINE 通知（任意）

リポジトリ **Settings → Secrets** に設定すると、Actions 成功後に損益上位を送信します。

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_IDS`

未設定ならスキップされます。

## 結果の見方

| 場所 | 内容 |
|------|------|
| **GitHub Pages** | スマホ向けサマリー |
| **Actions ログ** | 実行詳細・エラー |
| **output/results/** | Actions 内で生成（リポジトリには含めない） |

## トラブル時

| 症状 | 確認 |
|------|------|
| Actions が赤 | ログの末尾。yfinance / 解析失敗が多い |
| サイトが更新されない | 直近 workflow が成功したか。Pages デプロイ 1〜2 分待つ |
| DB 競合 | ローカルで screening していないか |

---

## 参考: ローカル実行（開発・緊急時のみ）

`bat/` / `sh/` は **開発・デバッグ用**として残しています。本番では使わないでください。

| bat / sh | 用途（開発のみ） |
|----------|------------------|
| `healthcheck.bat` | 環境確認 |
| `screening.bat` | **本番では使わない** |

旧 bat 名の互換ラッパーも同様です。
