"""Every committed problem file must be loadable and consistent."""
import json
from pathlib import Path

import pytest
from pensionlab.lab import db
from pensionlab.lab.topics import TOPICS, canonical
from pensionlab.lab.verifiers import KEYED

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted((ROOT / "problems").glob("iaj-*.json"))
LEDGER = {s["id"]: s for s in json.load(open(ROOT / "sources/ledger.json", encoding="utf-8"))}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_problem_file(path):
    items = json.load(open(path, encoding="utf-8"))
    year = int(path.stem.split("-")[1])
    assert len({i["id"] for i in items}) == len(items)
    assert sum(i["points"] for i in items) == 100
    for i in items:
        assert canonical(i["topic"]) in TOPICS, (i["id"], i["topic"])
        assert "要約未作成" not in i["statement"], i["id"]
        assert i["verifier_id"] in KEYED and i["year"] == year
        src = LEDGER[i["source_id"]]
        assert src["url"].endswith(f"{year}D.pdf") and src["verification"] == "verified"
        assert i["page"] and i["answer_page"] and i["page"] < i["answer_page"]
        for h in i.get("hints", []):
            assert h.strip() and len(h) < 200, i["id"]
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    assert db.load_problems(c, str(path)) == len(items)
