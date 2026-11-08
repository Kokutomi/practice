# Pension Math Lab（年金数理 Learning Lab）

日本アクチュアリー会 第1次試験「年金数理」の学習アプリと、年金数理の計算ライブラリ。

## 起動

```
pip install -e '.[app]'
PYTHONPATH=src streamlit run src/pensionlab/lab/app.py
```

起動時に `problems/` の全問題と `sources/ledger.json` を自動で読み込みます（ファイルが更新されていれば再読み込み）。
学習記録は作業ディレクトリの `data/lab.sqlite`（git 管理外）に保存されます。サイドバーからバックアップできます。

## スマホで使う

Streamlit Community Cloud に無料で公開できます（エントリーポイントは `streamlit_app.py`、依存関係は `requirements.txt`）。
手順と注意点（学習記録はバックアップ必須、public リポジトリのアプリは既定で公開）は [docs/DEPLOY.md](docs/DEPLOY.md)。

## 画面

| 画面 | できること |
|---|---|
| 演習 | 1欄ずつ解答。選択・全選択・数字穴埋めに対応。年度・分野・出題元・状態（復習期限／未解答／前回誤答／自信なし／今日のおすすめ）で絞り込み。段階的ヒント、公式PDFの問題・解答例ページへのリンク、教科書の該当節へのリンク、誤答ノート |
| 本番モード | 年度を通しでマークシート形式に解答、制限時間（既定180分）、配点・完答ルールで採点 |
| ダッシュボード | 今日のおすすめ、年度別得点、分野別正答率と解答時間、1点あたりの解答ペース、確信度×正誤、本番履歴、Anki・Obsidian 書き出し |
| 学習計画 | 試験日（2026-12-09 10:00）までの日次計画。土曜（必要なら日曜）10:00〜13:00 に過去問を通しで解く。`.ics` でカレンダーに取り込み |
| 計算ツール | 計算基数表、年金現価（確定・終身・据置・保証期間付）、Trowbridge モデルの財政方式比較 |

## 収録データ

- `problems/iaj-2019.json` 〜 `iaj-2025.json`：日本アクチュアリー会「年金数理」2019〜2025年度、計324解答欄。
  公式正答・配点・完答グループ・問題/解答例ページ・分野・自作の一行要約。2024・2025年度は自作の解き方ヒント付き。
- `problems/sample.json`：自作の計算問題（`pensionlab` で再計算して判定）。
- `sources/ledger.json`：出典台帳（URL・取得日時・版・検証状態・利用条件）。

**問題文は収録していません。** 公式PDFへのリンクで参照します。リポジトリに入れるのは正答・配点などの事実と自作の要約・ヒントだけで、
PDF や問題文を手元に置く場合は git 管理外の `data/` に保存します。

## 過去問の追加

```
python tools/import_iaj.py 2018 --fetch          # PDF を data/sources/ に取得し、正答表・配点・ページを解析
# problems/annotations/iaj-2018.json に分野・要約・ヒントを書いて再実行
python tools/mark_verified.py 2018 "<Last-Modified>" "<取得日時>"
```

正答表が画像の年度（2018年度など）は推測せずエラーにします。注記「〜は順不同」は annotations の `answer` で上書きします。

## CLI

```
python -m pensionlab.lab.cli sources load sources/ledger.json
python -m pensionlab.lab.cli load problems/iaj-2025.json
python -m pensionlab.lab.cli practice | stats | score 2025
python -m pensionlab.lab.cli anki data/anki_review.txt     # 誤答・自信なしの欄を Anki 用に
python -m pensionlab.lab.cli notes ~/Obsidian/Vault        # 誤答ノートを Markdown で
python -m pensionlab.lab.cli backup save data/backup.json  # backup load FILE [replace]
```

## 計算ライブラリ（`pensionlab`）

- `mortality`：生命表、Gompertz–Makeham
- `annuities` / `commutation`：生命年金現価、計算基数（D, N, C, M）、確定年金（年m回払い）、保証期間付終身年金。
  確定年金現価率は 2025年度試験の問題文に掲載された値（9.16、56.50204 など）と一致することをテストで確認
- `finance`：Trowbridge モデルの5つの財政方式（賦課・退職時年金現価・単位・平準・加入時）の保険料と積立金。
  収支相等式、将来法＝過去法、積立金の大小関係をテストで確認

## テスト

```
pip install -e '.[dev]'
pytest
```
