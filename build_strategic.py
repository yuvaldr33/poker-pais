"""בונה את האתר "צ'אנס אסטרטגי" ל-docs/chance/ (GitHub Pages).

רשימת ההגרלות הקבועה: strategic/draws.json (מהחדשה לישנה).
היא מתעדכנת משני מקורות:
  1. המשימה המתוזמנת של Claude, שמוסיפה כל הגרלה חדשה כמה דקות אחרי שהיא נערכת.
  2. הארכיון הציבורי github.com/laly100/chance-feed (גיבוי, מתעדכן באיחור).
האתר עצמו בודק כל דקה אם יש draws.json חדש ומעדכן את הניתוח בלי רענון.
הרצה ידנית: python build_strategic.py
"""
import csv, datetime as dt, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "strategic")
OUT = os.path.join(HERE, "docs", "chance")
CANON = os.path.join(SRC, "draws.json")
FEED = "https://raw.githubusercontent.com/laly100/chance-feed/main/chance.csv"
KEEP = 2000
VALUES = {"7", "8", "9", "10", "J", "Q", "K", "A"}
SCHEDULE = {d: ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00"] for d in range(5)}  # 0=ראשון
SCHEDULE[5] = ["10:00", "12:00", "14:00"]
SCHEDULE[6] = ["21:30", "23:30"]


def valid(r):
    return all(r.get(k) in VALUES for k in "SHDC") and isinstance(r.get("n"), int)


def from_feed():
    try:
        import requests
        r = requests.get(FEED, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print("הארכיון לא זמין:", e)
        return []
    rows = []
    for x in csv.reader(io.StringIO(r.content.decode("utf-8-sig"))):
        if len(x) < 6 or not x[1].strip().isdigit():
            continue
        d = dt.datetime.strptime(x[0].strip(), "%d/%m/%Y").date()
        c, di, h, s = (v.strip() for v in x[2:6])
        rows.append(dict(n=int(x[1]), date=d.isoformat(), time="", S=s, H=h, D=di, C=c))
    rows = [r for r in rows if valid(r)]
    rows.sort(key=lambda r: -r["n"])
    rows = rows[:KEEP + 20]
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    for day, lst in by_day.items():
        lst.sort(key=lambda r: r["n"])
        slots = SCHEDULE[(dt.date.fromisoformat(day).weekday() + 1) % 7]
        if len(lst) == len(slots) or day == rows[0]["date"]:
            for r, t in zip(lst, slots):
                r["time"] = t
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    canon = json.load(open(CANON, encoding="utf-8")) if os.path.exists(CANON) else []
    by_n = {r["n"]: r for r in canon if valid(r)}
    for r in from_feed():                       # הארכיון ממלא חורים; לא דורס שורות קיימות
        if r["n"] not in by_n or by_n[r["n"]].get("src") == "m":   # תוצאה שהוזנה ידנית מוחלפת ברשמית
            if r["n"] in by_n and not r.get("time"):
                r["time"] = by_n[r["n"]].get("time", "")
            by_n[r["n"]] = r
        elif not by_n[r["n"]].get("time") and r["time"]:
            by_n[r["n"]]["time"] = r["time"]
    rows = sorted(by_n.values(), key=lambda r: -r["n"])
    # רק רצף בלי חורים מהחדשה אחורה
    clean = [rows[0]]
    for r in rows[1:]:
        if r["n"] != clean[-1]["n"] - 1:
            break
        clean.append(r)
    rows = clean[:KEEP]
    data = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    json.dump(rows, open(CANON, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    os.makedirs(OUT, exist_ok=True)
    tpl = open(os.path.join(SRC, "template.html"), encoding="utf-8").read()
    head = open(os.path.join(SRC, "head.html"), encoding="utf-8").read()
    import hashlib
    build = hashlib.sha1((head + tpl).encode("utf-8")).hexdigest()[:10]   # משתנה רק כשהעיצוב/הקוד משתנה
    html = head + tpl.replace("__DATA__", data).replace("__BUILD__", build) + "\n</body>\n</html>\n"
    open(os.path.join(OUT, "version.json"), "w", encoding="utf-8").write(json.dumps({"build": build}))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(OUT, "draws.json"), "w", encoding="utf-8").write(data)
    hist = os.path.join(SRC, "history.txt")
    if os.path.exists(hist):
        open(os.path.join(OUT, "history.txt"), "w", encoding="utf-8").write(open(hist, encoding="utf-8").read())
    for f in ("manifest.webmanifest", "icon.svg"):
        open(os.path.join(OUT, f), "w", encoding="utf-8").write(open(os.path.join(SRC, f), encoding="utf-8").read())
    print(f"צ'אנס אסטרטגי: הגרלה אחרונה {rows[0]['n']} ({rows[0]['date']} {rows[0]['time']}), {len(rows)} הגרלות")


if __name__ == "__main__":
    main()
