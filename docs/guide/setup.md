# セットアップ

## 前提

- Python 3.10 以上推奨
- **Windows:** `bat/`（cmd / PowerShell）
- **Linux / macOS:** `sh/` または Makefile（[linux.md](linux.md)）
- Git（GitHub Pages 自動 push を使う場合）

## 1. リポジトリの取得

```bat
git clone <repository-url>
cd KabuRadar3
```

## 2. Python 環境

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. データベース

`data/kaburadar.db` は **Git LFS** でリポジトリに含まれます（clone 後に `git lfs pull`）。

```bash
git lfs install
git lfs pull
```

初回から DB が無い場合のみ、手元の `KabuRadar.db` を `data/kaburadar.db` にコピーして LFS で commit します。  
詳細: [data/README.md](../../data/README.md) · [無料クラウド実行](cloud.md)

## 4. 環境変数（任意）

```bat
copy .env.example .env
```

`.env` を編集します。解析だけなら不要です。

### LINE 通知の設定（任意）

**KabuRadar v1 から移植する場合**（`software/src/line.py` と同じ設定）:

```bash
python scripts/sync_line_from_kaburadar.py --env
```

クラウド用に GitHub Secrets へも入れる: 同コマンドに `--gh-secrets` を付ける（[cloud.md](cloud.md) 参照）。

手動で新規作成する場合:

1. [LINE Developers](https://developers.line.biz/) で Messaging API チャネルを作成
2. チャネルアクセストークンを `LINE_CHANNEL_ACCESS_TOKEN` に設定
3. 自分のユーザー ID を `LINE_USER_IDS` に設定（カンマ区切りで複数可）
4. 動作確認:

```bat
bat\screening_notify.bat
```

週末は送信されません。未設定のときは「LINE: .env 未設定のため送信しません。」と表示され、解析は続行します。

### Git push ブランチ（任意）

デフォルトブランチが `main` のリポジトリでは通常は自動検出されます。明示する場合:

```
KABURADAR_GIT_BRANCH=master
```

## 5. 動作確認

```bat
set PYTHONPATH=src
pytest
python src\kaburadar\cli\publish.py
```

`output\results\` に過去の集計 CSV がある場合、`publish` が `docs\data.json` を生成します。

## 6. GitHub Pages（初回のみ）

リポジトリの **Settings → Pages** で:

- Branch: `gh-pages`
- Folder: `/ (root)`

`bat\publish.bat --push` または `bat\analyze_and_publish.bat` 実行後、Actions が `gh-pages` ブランチを更新します。
