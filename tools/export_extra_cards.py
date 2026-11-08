"""python tools/export_extra_cards.py [OUT]  -> Anki import file of problems/anki/extra_cards.json.

In Anki: File > Import, choose the file, note type "Basic" (表面/裏面), deck 年金数理. Formulas use MathJax.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pensionlab.lab.cards import anki_tsv  # noqa: E402

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/anki/追加公式カード_Anki取込用.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(anki_tsv(), encoding="utf-8")
    print(out)
