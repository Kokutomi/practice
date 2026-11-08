# Pension Math Lab

Small stdlib-only Python playground for pension / life-contingency math.

- `mortality.py` – `LifeTable`, Gompertz–Makeham q_x generator
- `annuities.py` – annuity-due/immediate, deferred annuity, pension PV

```
pip install -e . pytest
pytest
```

Ideas: commutation functions, salary-scale accrued benefit (PUC), real mortality tables, Monte Carlo longevity.
