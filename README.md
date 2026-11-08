# Pension Math Lab

Small stdlib-only Python playground for pension / life-contingency math.

- `mortality.py` – `LifeTable`, Gompertz–Makeham q_x generator
- `annuities.py` – annuity-due/immediate, deferred annuity, pension PV

```
pip install -e . pytest
pytest
```

Practice screen (Streamlit):

```
pip install -e '.[app]'
PYTHONPATH=src streamlit run src/pensionlab/lab/app.py
```

Sidebar: load sample problems, per-topic stats, due reviews. Main: problem, staged hints, answer + confidence, recomputed verdict, error-type log.

Source ledger (`sources/ledger.json`):

```
python -m pensionlab.lab.cli sources load sources/ledger.json
python -m pensionlab.lab.cli sources list P0      # by priority
python -m pensionlab.lab.cli sources recheck      # problems whose source was replaced
```

Each source records kind, exam_body (IAJ = 日本アクチュアリー会 / JSCPA = 日本年金数理人会),
year, url, retrieved_at, version, verification, license, access, priority.
Problems link to it via `source_id` and carry `exam_body` / `question_no`.
Only metadata and links are committed; PDFs and problem text from official sources stay in `data/` (git-ignored).

Official past exams (`problems/iaj-2025.json`):

2025年度 日本アクチュアリー会「年金数理」を小問（解答欄）単位で36件登録。
各件は question_no・分野・配点・完答グループ・公式PDFの問題/解答例ページ・公式正答（2026-10-29 差替版）を持ち、
問題文そのものは収録せず公式PDFへのリンクで参照する（`statement` は自作の一行要約）。
問題2(4)(ア) は訂正により (F)(G) どちらも正解として判定する。

```
python -m pensionlab.lab.cli sources load sources/ledger.json
python -m pensionlab.lab.cli load problems/iaj-2025.json
python -m pensionlab.lab.cli practice      # 選択肢を A〜L で回答
```

Ideas: commutation functions, salary-scale accrued benefit (PUC), real mortality tables, Monte Carlo longevity.
