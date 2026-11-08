"""Study plan up to the exam date, exportable as an iCalendar (.ics) file.

- Saturdays (and Sundays if more mocks remain): a full-year mock exam at the real exam time,
  newest year first, skipping years already taken in exam mode.
- Weekday evenings: due reviews + new slots from the weakest / least-covered topics.
- The last two days before the exam: formula review only. Then the exam itself.
"""
from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone

from .topics import canonical

EXAM_DATE = date(2026, 12, 9)          # 2026年度 年金数理 12/9(水) 10:00〜 180分
EXAM_START = "10:00"
EXAM_MIN = 180


def _topic_load(con):
    """Topic -> [unattempted official slots, accuracy or None]."""
    load: dict[str, list] = {}
    tried = {r[0] for r in con.execute("SELECT DISTINCT problem_id FROM attempts")}
    for p in con.execute("SELECT id, topic FROM problems WHERE exam_body='IAJ'"):
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

    load = _topic_load(con)
    weekdays = [d for d in study if d not in mocks]
    remaining = sum(v[0] for v in load.values())
    per = slots_per_session or max(4, math.ceil(remaining / max(1, len(weekdays))))

    def weight(t):
        n, acc = load[t]
        return n * (2 - (acc if acc is not None else 0.5))

    plan = []
    for d in days:
        if d in review_days:
            plan.append({"date": d, "kind": "review", "title": "総復習：公式・誤答ノート",
                         "detail": "新しい問題は解かず、誤答ノートと公式集を確認。前日は早めに休む。",
                         "start": weekday_time, "minutes": weekday_min})
        elif d in mocks:
            y = mocks[d]
            plan.append({"date": d, "kind": "mock", "title": f"本番演習：{y}年度（{EXAM_MIN}分）",
                         "detail": f"Learning Lab の本番モードで {y}年度を通しで解く。終了後は誤答を復習キューへ。",
                         "start": mock_time, "minutes": EXAM_MIN})
        else:
            cands = [t for t in load if load[t][0] > 0]
            if cands:
                t = max(cands, key=weight)
                k = min(per, load[t][0])
                load[t][0] -= k
                title, detail = f"演習：{t}（{k}欄）＋復習", f"復習期限の問題を先に。その後「分野」で {t} を絞り込み {k}欄。"
            else:
                title, detail = "演習：復習と誤答の解き直し", "状態「前回誤答」「前回自信なし」で解き直し。"
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
