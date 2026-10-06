"""גרסת הענן: מעדכן תוצאות ובונה את docs/ לאתר סטטי (GitHub Pages).

רץ אוטומטית ב-GitHub Actions כל כמה דקות. אפשר גם להריץ ידנית: python build_site.py
"""
import json
import os
import shutil
import sys

import server

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(DOCS, exist_ok=True)
    for name in os.listdir(server.APP_DIR):
        shutil.copy2(os.path.join(server.APP_DIR, name), os.path.join(DOCS, name))
    server.cache["fetched"] = 0                     # תמיד לבדוק אם יש תוצאות חדשות
    state = server.build_state()
    state.pop("now", None)          # בענן הטלפון משתמש בשעון שלו; כך נשמר שינוי רק כשבאמת יש חדש
    with open(os.path.join(DOCS, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    print(f"עודכן: הגרלה אחרונה #{state['last']['draw']}, הבאה #{state['next']['draw']} ב-{state['next']['label']}")


if __name__ == "__main__":
    main()
