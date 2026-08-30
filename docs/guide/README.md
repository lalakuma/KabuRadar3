# KabuRadar3 ドキュメント

短期 RSI（`SCR_JDG_RSI4`）戦略のバックテスト・集計・GitHub Pages 公開ツールの説明です。

## 目次

| ドキュメント | 内容 |
|--------------|------|
| **[クラウド運用](cloud.md)** | **本番（Actions 専用）** |
| **[取扱説明書](manual.md)** | 全体の使い方 |
| [セットアップ](setup.md) | 初回環境構築・DB 配置 |
| [Linux / macOS](linux.md) | `sh/`・Makefile・cron |
| [無料クラウド実行](cloud.md) | GitHub Actions + Git LFS |
| [日常運用](operations.md) | bat / CLI の使い方 |
| [設定リファレンス](configuration.md) | `config_lo.ini` の各項目 |
| [アーキテクチャ](architecture.md) | ディレクトリ構成・処理フロー |
| [開発・テスト](development.md) | pytest・コーディング方針 |
| [変更履歴メモ](changelog.md) | リファクタ・整理の概要 |

**開発者向け:** リポジトリを修正するときは上記ドキュメントもあわせて更新してください（[development.md](development.md#ドキュメントを直すタイミング)）。

## クイックリンク

- リポジトリ README: [../../README.md](../../README.md)
- 設定ファイル: [../../config/config_lo.ini](../../config/config_lo.ini)
- データベース: [../../data/README.md](../../data/README.md)
