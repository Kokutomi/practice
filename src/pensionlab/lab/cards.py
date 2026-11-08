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
"""


def ensure_schema(con) -> None:
    con.executescript(SCHEMA)


def store(con, data: dict) -> int:
    """Replace the stored cards with a cards.json document. Topics come from problems/anki/topics.json
    when it knows the card (so a re-classification there applies without re-importing)."""
    if data.get("format") != "pensionlab-anki/1":
        raise ValueError("not a formula-card file")
    ensure_schema(con)
    topics = json.loads(TOPICS.read_text(encoding="utf-8")) if TOPICS.is_file() else {}
    con.execute("DELETE FROM formula_cards")
    for c in data["cards"]:
        con.execute("INSERT INTO formula_cards VALUES(?,?,?,?,?,?,?)",
                    (c["guid"], c["ord"], c.get("num", ""), c.get("kind", "basic"),
                     topics.get(c["guid"], c.get("topic")), c["front"], c["back"]))
    con.commit()
    return len(data["cards"])


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
