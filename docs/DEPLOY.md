# スマホで使う：Streamlit Community Cloud への公開手順

所要時間 5〜10分。無料。GitHub アカウント（Kokutomi）でログインします。

## 1. アプリを作る

1. https://share.streamlit.io を開き、**Continue with GitHub** でログイン（初回は GitHub 連携の許可画面が出ます）
2. 右上の **Create app** →「**Deploy a public app from GitHub**」
3. 次のとおり入力

   | 項目 | 入力値 |
   |---|---|
   | Repository | `Kokutomi/practice` |
   | Branch | `claude/laughing-ritchie-9d2s3q` |
   | Main file path | `streamlit_app.py` |
   | App URL | 好きな名前（例：`kou-nenkin`）→ `https://kou-nenkin.streamlit.app` |

4. **Advanced settings** で Python version を **3.12** にする
5. **Deploy** を押す。初回は依存関係のインストールで 2〜3 分かかります

このブランチに push すると、アプリは自動で更新されます。

## 2. iPhone のホーム画面に置く

Safari でアプリの URL を開く → 共有ボタン →「**ホーム画面に追加**」。アプリのように起動できます。

- 画面の切り替え（演習／本番モード／ダッシュボード／学習計画／計算ツール）は画面上部にあります
- 絞り込みとバックアップは左上の「»」で開くサイドバーにあります
- 問題文は「問題文を公式PDFで開く」から、アクチュアリー会の PDF を別タブで開きます

## 3. 学習記録について（重要）

- 記録はアプリのサーバー上の SQLite に保存されますが、**アプリが再起動・スリープ復帰・再デプロイされると消えます**
  （Community Cloud はしばらくアクセスがないとアプリをスリープさせます）
- **学習を終えたら、サイドバーの「学習記録のバックアップ」→「バックアップをダウンロード」** で JSON を保存してください
  （iPhone では「ファイル」アプリに保存されます）
- 記録が消えていたら、演習画面の上に「学習記録が空です…」と出るので、そこから JSON を選んで「復元する」
- Mac とスマホの両方で使う場合も、同じ JSON を読み込めば記録を引き継げます（重複は自動で除外）

## 4. 公開範囲について（重要）

このリポジトリは **public** です。public リポジトリから作ったアプリは、既定では **URL を知っている人なら誰でも開けます**。
また、学習記録はアプリに1つだけなので、開いた人全員が同じ記録を見たり書き換えたりできます。

- アプリの **Settings → Sharing** で閲覧者を自分（メールアドレス）だけに限定できるか確認してください
- 限定できない場合は、URL を他人に教えない、あるいはリポジトリを private にしてからデプロイし直すことを検討してください
  （private リポジトリのアプリは既定で非公開になります）

## うまく動かないとき

- 「Error installing requirements」：Advanced settings の Python version を 3.12 にして **Reboot app**
- 画面が古いまま：右下の「Manage app」→ **Reboot app**
- それでも直らない場合は、Manage app のログを貼ってもらえれば原因を調べます
