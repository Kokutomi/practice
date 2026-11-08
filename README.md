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

Ideas: commutation functions, salary-scale accrued benefit (PUC), real mortality tables, Monte Carlo longevity.
