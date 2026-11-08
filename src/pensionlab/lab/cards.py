"""Formula cards from the learner's Anki deck (.apkg), shown per topic in the app.

    python tools/import_anki.py path/to/年金数理.apkg      # writes data/anki/cards.json (PC)

On the phone (Streamlit Cloud) the .apkg or cards.json is uploaded from the sidebar instead.

The deck's text and images are NOT committed (data/ is git-ignored); only the card -> topic table
problems/anki/topics.json is. Cards are stored self-contained: Anki's pre-rendered LaTeX images (SVG) and
pictures are embedded as data URIs, MathJax \\( \\) / \\[ \\] is turned into $ / $$ for Streamlit, and
cloze deletions become a blank on the front and a highlighted answer on the back.

Both the legacy (collection.anki2) and the current zstd-compressed (collection.anki21b) formats are read;
the latter needs the `zstandard` package.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOPICS = ROOT / "problems" / "anki" / "topics.json"
OUT = ROOT / "data" / "anki" / "cards.json"
EXTRA = ROOT / "problems" / "anki" / "extra_cards.json"      # own cards for topics the deck lacks (committed)
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
SCALE = 0.72                     # formula image size relative to how Anki rendered it

LATEX = re.compile(r"\[\$\$\](.+?)\[/\$\$\]|\[\$\](.+?)\[/\$\]|\[latex\](.+?)\[/latex\]", re.S)
CLOZE = re.compile(r"\{\{c(\d+)::(.+?)(?:::(.*?))?\}\}", re.S)
MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}


def _unzstd(data: bytes) -> bytes:
    if not data.startswith(ZSTD_MAGIC):
        return data
    import zstandard
    return zstandard.ZstdDecompressor().stream_reader(data).read()


def _varint(b: bytes, i: int):
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return r, i


def _pb_fields(b: bytes):
    """Minimal protobuf reader (enough for Anki's media list)."""
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        f, t = key >> 3, key & 7
        if t == 0:
            v, i = _varint(b, i)
        elif t == 2:
            n, i = _varint(b, i)
            v, i = b[i:i + n], i + n
        elif t == 5:
            v, i = b[i:i + 4], i + 4
        elif t == 1:
            v, i = b[i:i + 8], i + 8
        else:
            raise ValueError(f"protobuf wire type {t}")
        yield f, v


def media_map(z: zipfile.ZipFile) -> dict[str, bytes]:
    """{file name: bytes} for every media file in the package."""
    raw = _unzstd(z.read("media"))
    if raw.lstrip().startswith(b"{"):                       # legacy: JSON {"0": "name", ...}
        names = {int(k): v for k, v in json.loads(raw).items()}
    else:                                                    # current: protobuf MediaEntries
        names = {}
        for idx, (f, v) in enumerate(x for x in _pb_fields(raw) if x[0] == 1):
            entry = dict(_pb_fields(v))
            names[idx] = entry[1].decode("utf-8")
    return {name: _unzstd(z.read(str(i))) for i, name in names.items() if str(i) in z.namelist()}


def _strip_for_latex(t: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).replace("\xa0", " ")


def latex_fname(m: re.Match) -> str:
    """Anki's file name for a rendered [$]..[/$] / [$$]..[/$$] / [latex] block (SVG)."""
    if m.group(1) is not None:
        body = "\\begin{displaymath}" + _strip_for_latex(m.group(1)) + "\\end{displaymath}"
    elif m.group(2) is not None:
        body = "$" + _strip_for_latex(m.group(2)) + "$"
    else:
        body = _strip_for_latex(m.group(3))
    return "latex-" + hashlib.sha1(body.encode("utf-8")).hexdigest() + ".svg"


def _data_uri(name: str, data: bytes) -> str:
    return f"data:{MIME.get(Path(name).suffix.lower(), 'application/octet-stream')};base64," + \
        base64.b64encode(data).decode("ascii")


def render(field: str, media: dict[str, bytes], missing: list[str]) -> str:
    """Anki field HTML -> self-contained HTML/Markdown for st.markdown(unsafe_allow_html=True)."""
    def latex_img(m):
        fn = latex_fname(m)
        if fn not in media:
            missing.append(fn)
            src = m.group(1) or m.group(2) or m.group(3)
            return f"<code>{html.escape(_strip_for_latex(src))}</code>"
        display = m.group(1) is not None
        style = "background:#fff;padding:2px 4px;border-radius:4px;vertical-align:middle;max-width:100%"
        size = re.search(rb'<svg[^>]*?\swidth=["\']([\d.]+)pt["\']', media[fn][:2000])
        if size:                                     # Anki renders at 12pt; shrink to sit with body text
            style += f";width:{float(size.group(1)) * SCALE:.1f}pt"
        img = f'<img class="lab-tex" style="{style}" src="{_data_uri(fn, media[fn])}">'
        return f'<div style="margin:6px 0">{img}</div>' if display else img

    s = LATEX.sub(latex_img, field)

    def pic(m):
        name = html.unescape(m.group(1))
        if name.startswith("data:"):
            return m.group(0)
        if name not in media:
            missing.append(name)
            return f"[画像なし: {html.escape(name)}]"
        return f'<img style="max-width:100%;background:#fff" src="{_data_uri(name, media[name])}">'

    s = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', pic, s)
    s = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", s, flags=re.S)
    s = re.sub(r"\\\[(.+?)\\\]", lambda m: "\n\n$$" + m.group(1).strip() + "$$\n\n", s, flags=re.S)
    return s.replace("&nbsp;", " ")


def cloze(text: str, reveal: bool) -> str:
    def rep(m):
        if reveal:
            return f'<span style="color:#1f6feb;font-weight:600">{m.group(2)}</span>'
        return f"<b>[{m.group(3) or '…'}]</b>"
    return CLOZE.sub(rep, text)


def _open_collection(z: zipfile.ZipFile, tmp: str) -> sqlite3.Connection:
    name = "collection.anki21b" if "collection.anki21b" in z.namelist() else (
        "collection.anki21" if "collection.anki21" in z.namelist() else "collection.anki2")
    path = os.path.join(tmp, "collection.sqlite")
    with open(path, "wb") as f:
        f.write(_unzstd(z.read(name)))
    return sqlite3.connect(path)


def convert(apkg: str, topics: dict[str, str]) -> dict:
    with zipfile.ZipFile(apkg) as z, tempfile.TemporaryDirectory() as tmp:
        media = media_map(z)
        con = _open_collection(z, tmp)
        try:
            kinds = {r[0]: r[1] for r in con.execute("SELECT id, name FROM notetypes")}
        except sqlite3.OperationalError:                       # legacy schema keeps notetypes in col.models
            kinds = {int(k): v["name"] for k, v in json.loads(con.execute("SELECT models FROM col").fetchone()[0]).items()}
        rows = con.execute("SELECT guid, mid, flds FROM notes ORDER BY id").fetchall()
        con.close()
    cards, missing = [], []
    for order, (guid, mid, flds) in enumerate(rows, 1):
        f = flds.split("\x1f")
        front, back = f[0], (f[1] if len(f) > 1 else "")
        num = re.sub(r"<[^>]+>", "", f[2]).strip() if len(f) > 2 else ""
        is_cloze = bool(CLOZE.search(front))
        if is_cloze:
            q, a = cloze(front, False), cloze(front, True) + ("<hr>" + back if back.strip() else "")
        else:
            q, a = front, back
        cards.append({"guid": guid, "ord": order, "num": num, "kind": "cloze" if is_cloze else "basic",
                      "notetype": kinds.get(mid, ""), "topic": topics.get(guid),
                      "front": render(q, media, missing), "back": render(a, media, missing)})
    return {"format": "pensionlab-anki/1", "source": Path(apkg).name, "cards": cards,
            "missing_media": sorted(set(missing))}


SCHEMA = """
CREATE TABLE IF NOT EXISTS formula_cards(
  guid TEXT PRIMARY KEY, ord INTEGER, num TEXT, kind TEXT, topic TEXT, front TEXT NOT NULL, back TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS card_reviews(        -- the learner's self-grading (kept in the backup)
  guid TEXT NOT NULL, reviewed_at REAL NOT NULL, grade TEXT NOT NULL, PRIMARY KEY(guid, reviewed_at));
CREATE TABLE IF NOT EXISTS card_state(
  guid TEXT PRIMARY KEY, due_at REAL NOT NULL, interval_days REAL NOT NULL, last_grade TEXT NOT NULL);
"""

# Self-grading of a formula card after revealing the answer, and the next review interval.
#   ◎ すらすら書けた: interval ×2.5 (first time 3 days)
#   ○ 思い出せたが迷った: interval ×1.2 (first time 2 days, at least 1 day)
#   △ 書けなかった: back tomorrow
GRADES = {"◎": 1.0, "○": 0.5, "△": 0.0}
DAY = 86400.0


def ensure_schema(con) -> None:
    con.executescript(SCHEMA)


def store(con, data: dict) -> int:
    """Replace the stored cards with a cards.json document. Topics come from problems/anki/topics.json
    when it knows the card (so a re-classification there applies without re-importing)."""
    if data.get("format") != "pensionlab-anki/1":
        raise ValueError("not a formula-card file")
    ensure_schema(con)
    topics = json.loads(TOPICS.read_text(encoding="utf-8")) if TOPICS.is_file() else {}
    con.execute("DELETE FROM formula_cards WHERE guid NOT LIKE 'x-%'")      # keep the own (extra) cards
    for c in data["cards"]:
        con.execute("INSERT INTO formula_cards VALUES(?,?,?,?,?,?,?)",
                    (c["guid"], c["ord"], c.get("num", ""), c.get("kind", "basic"),
                     topics.get(c["guid"], c.get("topic")), c["front"], c["back"]))
    con.commit()
    return len(data["cards"])


def sync_extra(con, path=EXTRA) -> int:
    """Load problems/anki/extra_cards.json (own cards, plain Markdown + KaTeX) when it changed."""
    ensure_schema(con)
    path = Path(path)
    if not path.is_file():
        return 0
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    row = con.execute("SELECT value FROM meta WHERE key='extra_cards_hash'").fetchone()
    if row and row[0] == digest:
        return 0
    data = json.loads(raw.decode("utf-8"))
    if data.get("format") != "pensionlab-extra-cards/1":
        raise ValueError("not an extra-card file")
    con.execute("DELETE FROM formula_cards WHERE guid LIKE 'x-%'")
    for n, c in enumerate(data["cards"], 1):
        if not c["id"].startswith("x-"):
            raise ValueError(f"extra card ids start with x-: {c['id']}")
        con.execute("INSERT INTO formula_cards VALUES(?,?,?,?,?,?,?)",
                    (c["id"], 100000 + n, "追加", "basic", c["topic"], c["front"], c["back"]))
    con.execute("INSERT OR REPLACE INTO meta VALUES('extra_cards_hash', ?)", (digest,))
    con.commit()
    return len(data["cards"])


def anki_tsv(path=EXTRA) -> str:
    """The own cards as an Anki import file (File > Import; Basic note type, MathJax)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    def mathjax(s: str) -> str:
        s = re.sub(r"\$\$(.+?)\$\$", lambda m: r"\[" + m.group(1) + r"\]", s, flags=re.S)
        s = re.sub(r"\$(.+?)\$", lambda m: r"\(" + m.group(1) + r"\)", s, flags=re.S)
        return html.escape(s, quote=False).replace("\n", "<br>").replace("\t", " ")

    lines = ["#separator:tab", "#html:true", "#tags column:3"]
    for c in data["cards"]:
        tag = "年金数理::追加::" + re.sub(r"[（）・\s]", "_", c["topic"])
        lines.append(f"{mathjax(c['front'])}\t{mathjax(c['back'])}\t{tag}")
    return "\n".join(lines) + "\n"


def load_upload(con, name: str, raw: bytes) -> int:
    """An uploaded .apkg or cards.json."""
    if name.lower().endswith(".apkg"):
        topics = json.loads(TOPICS.read_text(encoding="utf-8")) if TOPICS.is_file() else {}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "deck.apkg")
            with open(p, "wb") as f:
                f.write(raw)
            return store(con, convert(p, topics))
    return store(con, json.loads(raw.decode("utf-8")))


def sync(con, path=OUT) -> int:
    """Load data/anki/cards.json when its contents changed since the last load. Returns cards loaded."""
    ensure_schema(con)
    path = Path(path)
    if not path.is_file():
        return 0
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    row = con.execute("SELECT value FROM meta WHERE key='anki_cards_hash'").fetchone()
    if row and row[0] == digest:
        return 0
    n = store(con, json.loads(raw.decode("utf-8")))
    con.execute("INSERT OR REPLACE INTO meta VALUES('anki_cards_hash', ?)", (digest,))
    con.commit()
    return n


def review(con, guid: str, grade: str, now: float | None = None) -> float:
    """Record a self-grade and schedule the next review. Returns the new interval in days."""
    import time
    if grade not in GRADES:
        raise ValueError(grade)
    ensure_schema(con)
    now = time.time() if now is None else now
    prev = con.execute("SELECT interval_days FROM card_state WHERE guid=?", (guid,)).fetchone()
    if grade == "◎":
        interval = prev[0] * 2.5 if prev else 3.0
    elif grade == "○":
        interval = max(1.0, prev[0] * 1.2) if prev else 2.0
    else:
        interval = 1.0
    con.execute("INSERT OR REPLACE INTO card_reviews VALUES(?,?,?)", (guid, now, grade))
    con.execute("INSERT OR REPLACE INTO card_state VALUES(?,?,?,?)", (guid, now + interval * DAY, interval, grade))
    con.commit()
    return interval


def due(con, topic: str | None = None, now: float | None = None):
    """Cards whose review is due (graded before), most overdue first; optionally within one topic."""
    import time
    from .topics import canonical
    ensure_schema(con)
    now = time.time() if now is None else now
    q = ("SELECT c.*, s.due_at, s.last_grade FROM formula_cards c JOIN card_state s ON s.guid=c.guid"
         " WHERE s.due_at<=?")
    a: list = [now]
    if topic:
        q += " AND c.topic=?"
        a.append(canonical(topic))
    return con.execute(q + " ORDER BY s.due_at", a).fetchall()


def state(con, guid: str):
    ensure_schema(con)
    return con.execute("SELECT * FROM card_state WHERE guid=?", (guid,)).fetchone()


def mastery_by_topic(con) -> dict[str, dict]:
    """Topic -> {"graded": n, "total": n, "mastery": mean of the latest grade (◎1 ○0.5 △0) or None}."""
    ensure_schema(con)
    out: dict[str, dict] = {}
    for r in con.execute("SELECT c.topic, s.last_grade FROM formula_cards c LEFT JOIN card_state s ON s.guid=c.guid"):
        o = out.setdefault(r[0], {"graded": 0, "total": 0, "sum": 0.0})
        o["total"] += 1
        if r[1]:
            o["graded"] += 1
            o["sum"] += GRADES[r[1]]
    return {t: {"graded": o["graded"], "total": o["total"],
                "mastery": o["sum"] / o["graded"] if o["graded"] else None} for t, o in out.items()}


def for_topic(con, topic: str | None):
    from .topics import canonical
    ensure_schema(con)
    if topic is None:
        return con.execute("SELECT * FROM formula_cards ORDER BY ord").fetchall()
    return con.execute("SELECT * FROM formula_cards WHERE topic=? ORDER BY ord", (canonical(topic),)).fetchall()


def counts(con) -> dict[str, int]:
    ensure_schema(con)
    return {r[0]: r[1] for r in con.execute("SELECT topic, COUNT(*) FROM formula_cards GROUP BY topic")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("apkg")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    topics = json.loads(TOPICS.read_text(encoding="utf-8")) if TOPICS.is_file() else {}
    data = convert(a.apkg, topics)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    no_topic = sum(1 for c in data["cards"] if not c["topic"])
    print(f"{len(data['cards'])} cards -> {a.out} (no topic: {no_topic}, missing media: {len(data['missing_media'])})")


if __name__ == "__main__":
    main()
