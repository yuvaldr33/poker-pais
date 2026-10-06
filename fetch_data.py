"""הורדת תוצאות צ'אנס מאתר מפעל הפיס ושמירה ל-data/chance.csv.

כל שורה: מספר הגרלה, תאריך, שעה, ואז הערך בכל עמודה לפי סדר ♠ ♥ ♦ ♣.
הצורה משמשת רק לזיהוי העמודה (המיקום); נשמר רק הערך (7..A).
"""
import csv
import os
import re
import sys

import requests

URL = "https://www.pais.co.il/chance/showMoreResults.aspx"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chance.csv")

SUITS = ["spade", "heart", "diamond", "club"]          # סדר העמודות: ♠ ♥ ♦ ♣
IMG_TO_SUIT = {"peak": "spade", "hearth": "heart", "diamond": "diamond", "clubs": "club"}
VALUES = ["7", "8", "9", "10", "J", "Q", "K", "A"]

ITEM_RE = re.compile(r'<li class="archive_list_item chance[^"]*">(.*?)</li>', re.S)
NUM_RE = re.compile(r'chance_number".*?<div>(\d+)</div>', re.S)
DATE_RE = re.compile(r'(\d\d/\d\d/\d\d)\s*</div>.*?(\d\d:\d\d)', re.S)
CARD_RE = re.compile(r'ic_card_(\w+)\.png.*?</div>\s*<div>\s*([^<\s]+)\s*</div>', re.S)


def parse(html):
    draws = []
    for item in ITEM_RE.findall(html):
        num = NUM_RE.search(item)
        date = DATE_RE.search(item)
        cards = CARD_RE.findall(item)
        if not num or len(cards) != 4:
            continue
        by_suit = {IMG_TO_SUIT.get(img): val for img, val in cards}
        if set(by_suit) != set(SUITS) or not all(v in VALUES for v in by_suit.values()):
            continue
        draws.append({
            "draw": int(num.group(1)),
            "date": date.group(1) if date else "",
            "time": date.group(2) if date else "",
            **by_suit,
        })
    return draws


def load():
    if not os.path.exists(DATA):
        return []
    with open(DATA, encoding="utf-8") as f:
        return [{**r, "draw": int(r["draw"])} for r in csv.DictReader(f)]


def save(draws):
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    draws = sorted(draws, key=lambda d: d["draw"])
    with open(DATA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["draw", "date", "time"] + SUITS)
        w.writeheader()
        w.writerows(draws)


def update(target=3000, page=100, log=print):
    """מוריד הגרלות חדשות עד שמגיע להגרלה שכבר שמורה, או עד target הגרלות."""
    existing = {d["draw"]: d for d in load()}
    known_max = max(existing) if existing else 0
    added = 0
    start = 1
    while True:
        r = requests.get(URL, params={"fromIndex": start, "amount": page}, timeout=30)
        r.raise_for_status()
        batch = parse(r.text)
        if not batch:
            break
        for d in batch:
            if d["draw"] not in existing:
                existing[d["draw"]] = d
                added += 1
        start += page
        if min(d["draw"] for d in batch) <= known_max or len(existing) >= target:
            break
    save(existing.values())
    log(f"נוספו {added} הגרלות חדשות. סה\"כ שמורות: {len(existing)}")
    return load()


if __name__ == "__main__":
    update(target=int(sys.argv[1]) if len(sys.argv) > 1 else 3000)
