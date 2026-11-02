"""בונה את האתר "צ'אנס אסטרטגי" ל-docs/chance/ (GitHub Pages).

מקור התוצאות: הארכיון הציבורי github.com/laly100/chance-feed (chance.csv),
ואם יש הגרלה אחת חדשה יותר באתר chancestats.co.il, היא נוספת.
רץ אוטומטית ב-GitHub Actions. הרצה ידנית: python build_strategic.py
"""
import csv, datetime as dt, io, json, os, re, sys
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "chance")
FEED = "https://raw.githubusercontent.com/laly100/chance-feed/main/chance.csv"
LIVE = "https://chancestats.co.il/chance-2/"
KEEP = 300
VALUES = {"7", "8", "9", "10", "J", "Q", "K", "A"}
SCHEDULE = {d: ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00"] for d in range(5)}  # 0=ראשון
SCHEDULE[5] = ["10:00", "12:00", "14:00"]
SCHEDULE[6] = ["21:30", "23:30"]


def weekday_il(d):          # 0=ראשון ... 6=שבת
    return (d.weekday() + 1) % 7


def from_feed():
    r = requests.get(FEED, timeout=60)
    r.raise_for_status()
    rows = []
    for x in csv.reader(io.StringIO(r.content.decode("utf-8-sig"))):
        if len(x) < 6 or not x[1].strip().isdigit():
            continue
        d = dt.datetime.strptime(x[0].strip(), "%d/%m/%Y").date()
        c, di, h, s = (v.strip() for v in x[2:6])
        if {c, di, h, s} <= VALUES:
            rows.append(dict(n=int(x[1]), date=d.isoformat(), time="", S=s, H=h, D=di, C=c))
    rows.sort(key=lambda r: -r["n"])
    rows = rows[:KEEP + 20]
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    for day, lst in by_day.items():
        lst.sort(key=lambda r: r["n"])
        slots = SCHEDULE[weekday_il(dt.date.fromisoformat(day))]
        if len(lst) == len(slots) or day == rows[0]["date"]:
            for r, t in zip(lst, slots):
                r["time"] = t
    return rows


def from_live():
    try:
        html = requests.get(LIVE, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
    except Exception:
        return None
    m = re.search(r"מספר\s*(\d{5,})\s*</?[^>]*>?.*?מתאריך\s*(\d\d)\.(\d\d)\.(\d{4})\s*(\d\d:\d\d)", html, re.S)
    if not m:
        return None
    cards = {}
    for alt, key in (("עלה", "S"), ("לב", "H"), ("יהלום", "D"), ("תילתן", "C")):
        c = re.search(r'alt="' + alt + r'"[^>]*>\s*(?:</[^>]+>\s*)*([0-9JQKA]{1,2})', html)
        if c and c.group(1) in VALUES:
            cards[key] = c.group(1)
    if len(cards) != 4:
        return None
    return dict(n=int(m.group(1)), date=f"{m.group(4)}-{m.group(3)}-{m.group(2)}", time=m.group(5), **cards)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = from_feed()
    live = from_live()
    if live and live["n"] == rows[0]["n"] + 1:
        rows.insert(0, live)
    elif live and live["n"] == rows[0]["n"]:
        rows[0]["time"] = rows[0]["time"] or live["time"]
    rows = rows[:KEEP]
    tpl = open(os.path.join(HERE, "strategic", "template.html"), encoding="utf-8").read()
    head = open(os.path.join(HERE, "strategic", "head.html"), encoding="utf-8").read()
    body = tpl.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    os.makedirs(OUT, exist_ok=True)
    html = head + body + "\n</body>\n</html>\n"
    path = os.path.join(OUT, "index.html")
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    if html != old:
        open(path, "w", encoding="utf-8").write(html)
    for f in ("manifest.webmanifest", "icon.svg"):
        src = os.path.join(HERE, "strategic", f)
        open(os.path.join(OUT, f), "w", encoding="utf-8").write(open(src, encoding="utf-8").read())
    print(f"צ'אנס אסטרטגי: הגרלה אחרונה {rows[0]['n']} ({rows[0]['date']} {rows[0]['time']})")


if __name__ == "__main__":
    main()
