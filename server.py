"""שרת מקומי לאפליקציית "פוקר פייס".

מגיש את האפליקציה (תיקיית app) ומספק API:
  GET /api/state  -> הגרלה הבאה (מאתר הפיס), לוח ההגרלות של היום, תוצאות אחרונות,
                     ותחזית להגרלה הבאה לפי method.py.
הפעלה:  python server.py   ואז לפתוח http://127.0.0.1:8777
"""
import datetime as dt
import importlib
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import requests

import fetch_data
import method

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Jerusalem")
except Exception:                                   # אין מסד אזורי זמן: זמן מקומי של המחשב
    TZ = dt.datetime.now().astimezone().tzinfo

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(HERE, "app")
PRED_FILE = os.path.join(HERE, "data", "predictions.json")
PORT = 8777
NEXT_URL = "https://www.pais.co.il/include/getNextLotteryDate.ashx?type=3"

# לוח קבוע לפי היסטוריית ההגרלות (0=ראשון ... 6=שבת). חגים: הפיס הוא המקור הקובע.
SCHEDULE = {d: ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00", "21:00"] for d in range(5)}
SCHEDULE[5] = ["10:00", "12:00", "14:00"]
SCHEDULE[6] = ["21:30", "23:30"]

lock = threading.Lock()
cache = {"draws": fetch_data.load(), "fetched": 0.0, "next": None, "next_fetched": 0.0}


def now():
    return dt.datetime.now(TZ)


def ms(d):
    return int(d.timestamp() * 1000)


def il_weekday(d):
    return (d.weekday() + 1) % 7                      # בפייתון שני=0; אצלנו ראשון=0


def draw_dt(draw):
    try:
        return dt.datetime.strptime(f'{draw["date"]} {draw["time"]}', "%d/%m/%y %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return None


def next_from_pais():
    """מועד ההגרלה הבאה לפי אתר הפיס (מטמון של דקה)."""
    if time.time() - cache["next_fetched"] < 60 and cache["next"] and cache["next"] > now():
        return cache["next"]
    try:
        obj = requests.get(NEXT_URL, timeout=10).json()[0]
        cache["next"] = dt.datetime.strptime(obj["nextLottoryDate"], "%b %d, %Y %H:%M:%S").replace(tzinfo=TZ)
        cache["next_fetched"] = time.time()
    except Exception as e:                            # אין רשת: נשתמש בלוח הקבוע
        print("לא הצלחתי לקבל את מועד ההגרלה הבאה מהפיס:", e)
    return cache["next"]


def next_from_schedule(after):
    for add in range(8):
        day = (after + dt.timedelta(days=add)).date()
        for t in SCHEDULE[il_weekday(dt.datetime.combine(day, dt.time()))]:
            h, m = map(int, t.split(":"))
            cand = dt.datetime.combine(day, dt.time(h, m), tzinfo=TZ)
            if cand > after:
                return cand
    return None


def refresh_results(force=False):
    """מוריד תוצאות חדשות כשיש סיבה לחשוב שיצאה הגרלה (לא יותר מפעם בחצי דקה)."""
    draws = cache["draws"]
    last_t = draw_dt(draws[-1]) if draws else None
    expected = next_from_schedule(last_t) if last_t else None
    due = expected is None or now() >= expected + dt.timedelta(minutes=1)
    stale = time.time() - cache["fetched"] > (30 if due else 600)
    if force or stale:
        try:
            cache["draws"] = fetch_data.update(target=3000, log=lambda *_: None)
        except Exception as e:
            print("לא הצלחתי לעדכן תוצאות:", e)
        cache["fetched"] = time.time()


def load_preds():
    if os.path.exists(PRED_FILE):
        with open(PRED_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_preds(p):
    with open(PRED_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)


def score(pred, draw):
    picked = [(s, v) for s, v in pred["cards"].items() if v]
    hits = [s for s, v in picked if draw[s] == v]
    return {"hits": len(hits), "picked": len(picked), "hit_suits": hits}


def build_state():
    with lock:
        refresh_results()
        importlib.reload(method)                      # שינוי בשיטה נכנס בלי להפעיל מחדש את השרת
        draws = cache["draws"]
        last = draws[-1]
        n = now()

        nxt = next_from_pais()
        if not nxt or nxt < n - dt.timedelta(minutes=15):
            nxt = next_from_schedule(n)
        # הגרלה שכבר התקיימה אבל התוצאה שלה עוד לא פורסמה: היא "הבאה" (ממתינים לתוצאה)
        last_t = draw_dt(last)
        pending = next_from_schedule(last_t) if last_t else None
        if pending and pending <= n < pending + dt.timedelta(hours=1) and pending < nxt:
            nxt = pending
        next_no = last["draw"] + 1

        preds = load_preds()
        key = str(next_no)
        if key not in preds:
            p = method.predict(draws, next_no)
            preds[key] = {**p, "method": method.NAME, "demo": method.DEMO, "created": n.isoformat()}
            save_preds(preds)
        pred = preds[key]

        recent = []
        for d in reversed(draws[-20:]):
            p = preds.get(str(d["draw"]))
            recent.append({**d, "pred": p, "score": score(p, d) if p else None})

        scored = [r["score"] for r in recent if r["score"]]
        # לוח ההגרלות של היום; אם כולן הסתיימו, מציגים את היום של ההגרלה הבאה
        day = n.date()
        if not any(dt.datetime.combine(day, dt.time(*map(int, t.split(":"))), tzinfo=TZ) > n
                   for t in SCHEDULE[il_weekday(n)]):
            day = nxt.date()
        day_label = "היום" if day == n.date() else ("מחר" if day == n.date() + dt.timedelta(days=1)
                                                    else day.strftime("%d/%m"))
        slots = []
        for t in SCHEDULE[il_weekday(dt.datetime.combine(day, dt.time()))]:
            h, m = map(int, t.split(":"))
            sd = dt.datetime.combine(day, dt.time(h, m), tzinfo=TZ)
            done = any(d["time"] == t and draw_dt(d) and draw_dt(d).date() == day for d in draws[-15:])
            slots.append({"time": t, "at": ms(sd), "done": done})

        return {
            "now": ms(n),
            "next": {"draw": next_no, "at": ms(nxt), "label": nxt.strftime("%d/%m %H:%M")},
            "prediction": {**pred, "draw": next_no},
            "method": {"name": method.NAME, "description": method.DESCRIPTION, "demo": method.DEMO},
            "today": slots,
            "day_label": day_label,
            "last": last,
            "last_at": ms(draw_dt(last)) if draw_dt(last) else None,
            "recent": recent,
            "tracking": {"draws": len(scored), "hits": sum(s["hits"] for s in scored),
                         "picked": sum(s["picked"] for s in scored)},
        }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=APP_DIR, **kw)

    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path.startswith("/api/state"):
            try:
                body = json.dumps(build_state(), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(500, str(e))
            return
        super().do_GET()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    host = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"
    srv = ThreadingHTTPServer((host, PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"פוקר פייס רץ בכתובת {url}  (לסגירה: Ctrl+C)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
