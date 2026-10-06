"""הרצה יומית: מעדכן הגרלות מהפיס, מנתח, ופותח את הדוח בדפדפן.

שימוש:  python chance.py            (עדכון + ניתוח + פתיחת הדוח)
        python chance.py --no-fetch (ניתוח בלבד, בלי הורדה)
"""
import os
import sys
import webbrowser

import numpy as np

import analysis as A
import fetch_data
import report

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW = 1000          # כמה הגרלות אחורה לומדים
TEST = 300             # כמה הגרלות אחרונות שמורות לבדיקה בטבלת התבניות
TOP = 20


def load_custom_rules(X):
    path = os.path.join(HERE, "my_rules.txt")
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.split("#")[0].strip():
                continue
            try:
                rule = A.parse_rule(line)
                if rule:
                    out.append(A.evaluate_custom(X, rule))
            except (KeyError, ValueError) as e:
                out.append({"text": line.strip(), "error": f"לא הבנתי את '{e}'"})
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if "--no-fetch" not in sys.argv:
        print("מעדכן הגרלות מאתר מפעל הפיס...")
        fetch_data.update()
    draws = fetch_data.load()
    X = A.to_matrix(draws)
    print(f"מנתח {len(X)} הגרלות...")

    # טבלת תבניות: חיפוש על [-WINDOW, -TEST), מבחן על TEST האחרונות, ועבר על מה שלפני
    train = X[-WINDOW:-TEST]
    test = X[-TEST:]
    past = X[:-WINDOW]
    rules = A.mine(train)
    q = A.bh_qvalues([r["p"] for r in rules])
    n_sig = int((q < 0.05).sum())
    pp = sorted((r for r in rules if r["fam"] == "PP"), key=lambda r: r["p"])[:TOP]
    top, tot = [], {"test_hits": 0, "test_n": 0, "test_exp": 0.0,
                    "past_hits": 0, "past_n": 0, "past_exp": 0.0}
    for r in pp:
        v = A.rule_view(r)
        v["test_n"], v["test_hits"] = A.evaluate_rule(test, r["fam"], r["lag"], r["c"], r["t"])
        v["past_n"], v["past_hits"] = A.evaluate_rule(past, r["fam"], r["lag"], r["c"], r["t"])
        for k in ("test", "past"):
            tot[f"{k}_hits"] += v[f"{k}_hits"]
            tot[f"{k}_n"] += v[f"{k}_n"]
            tot[f"{k}_exp"] += v[f"{k}_n"] * r["base"]
        top.append(v)

    print("בדיקת ערבוב...")
    perm = A.permutation_test(train, rounds=200)
    print("סימולציה יומית (walk-forward)...")
    wf_pp = A.walk_forward(X, WINDOW, "PP")
    wf_ss = A.walk_forward(X, WINDOW, "SS")

    off = len(draws) - len(X)
    base_idx = len(draws) - WINDOW
    ctx = {
        "last": draws[-1], "n_draws": len(draws), "first_draw": draws[0]["draw"], "window": WINDOW,
        "forecast_pp": A.forecast(X, WINDOW, "PP"), "forecast_ss": A.forecast(X, WINDOW, "SS"),
        "wf_pp": wf_pp, "wf_ss": wf_ss, "perm": perm,
        "top_rules": top, "top_totals": tot, "n_rules": len(rules), "n_significant": n_sig,
        "train_range": (draws[base_idx + off]["draw"], draws[-TEST - 1]["draw"]),
        "test_n_draws": len(test), "past_n_draws": len(past),
        "custom": load_custom_rules(X),
    }
    out = os.path.join(HERE, "report.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report.build(ctx))
    print(f"הדוח מוכן: {out}")
    print(f"תוצאה כנה: {wf_pp['hits']} פגיעות מתוך {wf_pp['n']} (מזל: {wf_pp['expected']:.1f})")
    if "--no-open" not in sys.argv:
        webbrowser.open("file:///" + out.replace("\\", "/"))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
