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

Ideas: commutation functions, salary-scale accrued benefit (PUC), real mortality tables, Monte Carlo longevity.
