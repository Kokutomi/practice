"""Study plan up to the exam date, exportable as an iCalendar (.ics) file.

- Saturdays (and Sundays if more mocks remain): a full-year mock exam at the real exam time,
  newest year first, skipping years already taken in exam mode.
- Weekday evenings: due reviews + one topic per day, chosen by weakness × recent-exam frequency
  (wblink.topic_table: app accuracy, last year's workbook ◎/△, formula-card grades); a topic's n-th day
  counts 1/(n+1) so the days spread over the weak topics. The day lists unsolved past-exam slots of that
  topic (years not used for weekend mocks), workbook problems to redo and formula cards.
- Every study day also names formula cards to review: cards that are due first, then new cards of the
  day's topic (CARDS_PER_DAY in total).
- The last two days before the exam: formula review only (cards still graded △, workbook problems with
  △). Then the exam itself.
"""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone

from .topics import canonical

EXAM_DATE = date(2026, 12, 9)          # 2026年度 年金数理 12/9(水) 10:00〜 180分
EXAM_START = "10:00"
EXAM_MIN = 180
CARDS_PER_DAY = 15


def _topic_load(con, skip_years=()):
    """Topic -> [unattempted official slots, accuracy or None]. Years done as weekend mocks are left out."""
    load: dict[str, list] = {}
    tried = {r[0] for r in con.execute("SELECT DISTINCT problem_id FROM attempts")}
    for p in con.execute("SELECT id, topic, year FROM problems WHERE exam_body='IAJ'"):
        if p["year"] in skip_years:
            continue
        t = canonical(p["topic"] or "")
        load.setdefault(t, [0, None])
        if p["id"] not in tried:
            load[t][0] += 1
    for r in con.execute("SELECT p.topic, AVG(a.is_correct) acc FROM attempts a JOIN problems p ON p.id=a.problem_id"
                         " GROUP BY p.topic"):
        t = canonical(r["topic"] or "")
        if t in load:
            load[t][1] = r["acc"]
    return load


def build(con, today: date, exam_date: date = EXAM_DATE, weekday_time: str = "20:30", weekday_min: int = 60,
          mock_time: str = EXAM_START, slots_per_session: int | None = None):
    if today >= exam_date:
        return [{"date": exam_date, "kind": "exam", "title": "年金数理 本番", "detail": "", "start": EXAM_START,
                 "minutes": EXAM_MIN}]
    taken = {r[0] for r in con.execute("SELECT DISTINCT year FROM exam_sessions WHERE submitted_at IS NOT NULL")}
    mock_years = [r[0] for r in con.execute("SELECT DISTINCT year FROM problems WHERE exam_body='IAJ' ORDER BY year DESC")
                  if r[0] not in taken]
    days = [(today + timedelta(d)) for d in range((exam_date - today).days)]
    review_days = set(days[-2:])
    study = [d for d in days if d not in review_days]
    mock_days = [d for d in study if d.weekday() == 5 and d <= exam_date - timedelta(3)]
    extra = [d for d in study if d.weekday() == 6 and d <= exam_date - timedelta(3)]
    while len(mock_days) < len(mock_years) and extra:      # use Sundays too when there are more years than Saturdays
        mock_days.append(extra.pop(0))
    mock_days = sorted(mock_days)[: len(mock_years)]
    mocks = dict(zip(mock_days, mock_years))

    load = _topic_load(con, set(mocks.values()))
    weekdays = [d for d in study if d not in mocks]
    remaining = sum(v[0] for v in load.values())
    per = slots_per_session or max(4, math.ceil(remaining / max(1, len(weekdays))))

    from . import wblink
    info = {r["topic"]: r for r in wblink.topic_table(con)}
    index = wblink.load_index()

    def priority(t):
        """weakness × recent-exam frequency (wblink.topic_table); topics with no data count as half weak."""
        r = info.get(t)
        acc = load.get(t, [0, None])[1]
        weak = r["weakness"] if r and r["weakness"] is not None else (1 - acc if acc is not None else 0.5)
        return weak * ((r["frequency"] if r else 0.0) + 0.01)

    days_on: dict[str, int] = {}

    def weight(t):
        # spread repeats out: the n-th day on the same topic counts 1/(n+1)
        return priority(t) / (1 + days_on.get(t, 0))

    from . import cards
    card_pool: dict[str, list[str]] = {}
    seen_cards = {r[0] for r in con.execute("SELECT guid FROM card_state")}
    for c in cards.for_topic(con, None):
        if c["guid"] not in seen_cards and c["topic"]:
            card_pool.setdefault(c["topic"], []).append(c["num"] or c["guid"])
    n_due = len(cards.due(con, now=None)) if card_pool or seen_cards else 0

    def card_note(t: str | None) -> str:
        nonlocal n_due
        if not card_pool and not seen_cards:
            return ""
        take_due = min(n_due, CARDS_PER_DAY)
        n_due -= take_due
        new = card_pool.get(t, [])[: CARDS_PER_DAY - take_due] if t else []
        if t:
            card_pool[t] = card_pool.get(t, [])[len(new):]
        parts = ([f"復習期限{take_due}枚"] if take_due else []) + ([f"{t}の新規{len(new)}枚"] if new else [])
        return (" 公式カード: " + "＋".join(parts) + "（「公式カード」画面で◎○△を付ける）。") if parts else ""

    weak_wb: dict[str, list[str]] = {}
    for w in wblink.weak_workbook_problems(con, index, n=200):
        weak_wb.setdefault(canonical(w["entry"]["topic"]), []).append(w["entry"]["wb_id"])

    plan = []
    for d in days:
        if d in review_days:
            plan.append({"date": d, "kind": "review", "title": "総復習：公式・誤答ノート",
                         "detail": "新しい問題は解かず、誤答ノート、△の公式カード（「公式カード」画面の「今日の復習」）、"
                                   "ワークブックで△が残る問題の解き方を確認。前日は早めに休む。",
                         "start": weekday_time, "minutes": weekday_min})
        elif d in mocks:
            y = mocks[d]
            plan.append({"date": d, "kind": "mock", "title": f"本番演習：{y}年度（{EXAM_MIN}分）",
                         "detail": f"Learning Lab の本番モードで {y}年度を通しで解く。終了後は誤答を復習キューへ。",
                         "start": mock_time, "minutes": EXAM_MIN})
        else:
            # a topic is worth a day if it still has unsolved past-exam slots, workbook problems to redo or new cards
            cands = [t for t in info if load.get(t, [0])[0] > 0 or weak_wb.get(t) or card_pool.get(t)]
            if cands:
                t = max(cands, key=weight)
                days_on[t] = days_on.get(t, 0) + 1
                k = min(per, load.get(t, [0])[0])
                if k:
                    load[t][0] -= k
                    title = f"演習：{t}（{k}欄）＋復習"
                    detail = f"復習期限の問題を先に。その後「分野」で {t} を絞り込み {k}欄。"
                else:
                    title = f"演習：{t}（解き直し）＋復習"
                    detail = f"復習期限の問題を先に。{t}は未解答の過去問が残っていないので、前回誤答・自信なしの欄を解き直す。"
                redo = weak_wb.get(t, [])[:2]
                if redo:
                    weak_wb[t] = weak_wb[t][2:]
                    detail += " ワークブックの解き直し: " + "、".join(f"問題{i}" for i in redo) + "（昨年△）。"
                detail += card_note(t)
            else:
                title, detail = "演習：復習と誤答の解き直し", "状態「前回誤答」「前回自信なし」で解き直し。" + card_note(None)
            plan.append({"date": d, "kind": "practice", "title": title, "detail": detail,
                         "start": weekday_time, "minutes": weekday_min})
    plan.append({"date": exam_date, "kind": "exam", "title": "年金数理 本番",
                 "detail": "日本アクチュアリー会 2026年度資格試験（CBT）。開始10:00・180分。", "start": EXAM_START,
                 "minutes": EXAM_MIN})
    return plan


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """RFC 5545: lines longer than 75 octets are folded."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return [out[0]] + [" " + x for x in out[1:]]


def to_ics(plan, stamp: datetime | None = None) -> str:
    stamp = (stamp or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//pensionlab//study plan//JA", "CALSCALE:GREGORIAN",
             "BEGIN:VTIMEZONE", "TZID:Asia/Tokyo", "BEGIN:STANDARD", "DTSTART:19700101T000000",
             "TZOFFSETFROM:+0900", "TZOFFSETTO:+0900", "TZNAME:JST", "END:STANDARD", "END:VTIMEZONE"]
    for e in plan:
        h, m = map(int, e["start"].split(":"))
        start = datetime(e["date"].year, e["date"].month, e["date"].day, h, m)
        end = start + timedelta(minutes=e["minutes"])
        lines += ["BEGIN:VEVENT", f"UID:{uuid.uuid5(uuid.NAMESPACE_URL, 'pensionlab/' + start.isoformat())}",
                  f"DTSTAMP:{stamp}", f"DTSTART;TZID=Asia/Tokyo:{start:%Y%m%dT%H%M%S}",
                  f"DTEND;TZID=Asia/Tokyo:{end:%Y%m%dT%H%M%S}", f"SUMMARY:{_esc(e['title'])}",
                  f"DESCRIPTION:{_esc(e['detail'])}", f"CATEGORIES:{e['kind']}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(x for line in lines for x in _fold(line)) + "\r\n"
