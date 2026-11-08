# Windows PC で使う ＋ Obsidian 連携

## 1. 準備（初回だけ）
- Git for Windows、Python 3.12（「Add python.exe to PATH」にチェック）、Claude デスクトップアプリ
- Obsidian の保管庫が PC から見えること（例：iCloud for Windows で同期した
  `C:\Users\<名前>\iCloudDrive\iCloud~md~obsidian\Second Brain`、または Obsidian Sync の保存先）

## 2. 取得とインストール（PowerShell）
```powershell
cd $HOME
git clone -b claude/laughing-ritchie-9d2s3q https://github.com/Kokutomi/practice.git
cd practice
python -m venv .venv
.venv\Scripts\Activate.ps1          # エラー時は先に: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -e ".[app]"
```

## 3. 保管庫を指定して起動
```powershell
$env:LAB_OBSIDIAN_VAULT = "C:\Users\<名前>\iCloudDrive\iCloud~md~obsidian\Second Brain"
streamlit run streamlit_app.py
```
- ワークブック `WBnamachu_.pdf` は保管庫の中のどこにあっても自動で見つけます（コピー不要）。
  演習画面の「📒 ワークブック」で問題ページと手書き解答を表示します。
- 毎回の設定が面倒なら、Windows の「環境変数を編集」で `LAB_OBSIDIAN_VAULT` をユーザー環境変数に登録します。

## 4. 誤答ノートを保管庫へ
ダッシュボード →「Obsidian に書き出す」→「保管庫に直接書き出す」。保管庫に `年金数理/` フォルダができ、
1問1ノートと分野ごとの索引ページが作られます（CLI なら `python -m pensionlab.lab.cli notes`）。

- 各ノートには、教科書（PDF リンク）とワークブックの該当ページ `[[WBnamachu_.pdf#page=…]]` へのリンクが入り、
  Obsidian の中でそのページを開けます。
- ノート末尾の「ここから下は Obsidian で自由に書けます」の印より下に書いた内容は、再書き出ししても消えません。

## 5. PDF を使う作業を Claude に頼む
Claude デスクトップアプリの「Code」で `practice` フォルダを開き、保管庫のフォルダも読めるように指定して依頼します
（例：「過去問の各設問をワークブックの近い問題に対応づけて push して」）。
PDF・保管庫の中身はリポジトリ（public）には入れません。
