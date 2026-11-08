"""python tools/import_anki.py path/to/deck.apkg  -> data/anki/cards.json (see pensionlab.lab.cards)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pensionlab.lab.cards import main  # noqa: E402

if __name__ == "__main__":
    main()
