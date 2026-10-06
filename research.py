"""מחקר מעמיק: האם יש בהגרלות צ'אנס חוקיות כלשהי שאפשר לנצל?

1. סוללת בדיקות אקראיות (כמו שבודקים מכונות הגרלה):
   אחידות לכל מיקום, אחידות לאורך זמן (הטיית כדור פיזית), תלות בין מיקומים,
   תלות בין הגרלות עוקבות (פיגור 1..5), השפעת שעת ההגרלה.
2. בדיקה קדימה (walk-forward) של כל אסטרטגיית ניחוש נפוצה על 30,000 הגרלות.
"""
import csv
import os
import sys
from collections import Counter

import numpy as np
from scipy.stats import binom, chi2_contingency, chisquare

import analysis as A

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8")


def load(name="chance_full.csv"):
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, A.to_matrix(rows)


def line(title, p, extra=""):
    flag = "  <-- חשוד" if p < 0.001 else ""
    print(f"  {title:<48} p={p:.4f} {extra}{flag}")


def battery(rows, X):
    N = len(X)
    print(f"\n=== סוללת בדיקות אקראיות על {N:,} הגרלות ===")

    print("\n[1] אחידות: כל ערך מופיע 1/8 מהזמן בכל מיקום?")
    for p in range(4):
        cnt = np.bincount(X[:, p], minlength=8)
        line(f"מיקום {A.POS_NAME[p]}  (מינ' {cnt.min()}, מקס' {cnt.max()}, צפוי {N / 8:.0f})",
             chisquare(cnt).pvalue)

    print("\n[2] הטיה זמנית (כדור שחוק): אחידות בבלוקים של 2,000 הגרלות")
    ps = []
    for s in range(0, N - 1999, 2000):
        for p in range(4):
            ps.append(chisquare(np.bincount(X[s:s + 2000, p], minlength=8)).pvalue)
    ps = np.array(ps)
    print(f"  {len(ps)} בדיקות. p<0.01: {int((ps < .01).sum())} (צפוי ממזל {len(ps) * .01:.1f}),"
          f" p<0.001: {int((ps < .001).sum())} (צפוי {len(ps) * .001:.2f}), הקטן ביותר {ps.min():.4f}")

    print("\n[3] תלות בין מיקומים באותה הגרלה")
    for i, j in A.PAIRS:
        t = np.zeros((8, 8)); np.add.at(t, (X[:, i], X[:, j]), 1)
        line(f"{A.POS_NAME[i]} מול {A.POS_NAME[j]}", chi2_contingency(t).pvalue)

    print("\n[4] תלות בין הגרלות: האם הגרלה n משפיעה על n+L? (16 צירופי מיקום × 5 פיגורים)")
    ps = []
    for L in range(1, 6):
        for i in range(4):
            for j in range(4):
                t = np.zeros((8, 8)); np.add.at(t, (X[:-L, i], X[L:, j]), 1)
                ps.append(chi2_contingency(t).pvalue)
    ps = np.array(ps)
    print(f"  80 בדיקות. p<0.01: {int((ps < .01).sum())} (צפוי ממזל 0.8), הקטן ביותר {ps.min():.4f}"
          f" (אחרי תיקון בונפרוני: {min(1, ps.min() * 80):.3f})")
    same = (X[1:] == X[:-1]).mean()
    line(f"קלף חוזר באותו מיקום בהגרלה הבאה: {same:.4f} (צפוי 0.1250)",
         2 * min(binom.cdf((X[1:] == X[:-1]).sum(), (N - 1) * 4, 1 / 8),
                 binom.sf((X[1:] == X[:-1]).sum() - 1, (N - 1) * 4, 1 / 8)))

    print("\n[5] השפעת שעת ההגרלה")
    times = [r["time"] for r in rows]
    have = [k for k, v in Counter(times).items() if k and v > 500]
    if have:
        for p in range(4):
            t = np.array([[np.sum((X[:, p] == v) & (np.array(times) == h)) for v in range(8)] for h in have])
            line(f"מיקום {A.POS_NAME[p]} לפי {len(have)} שעות הגרלה", chi2_contingency(t).pvalue)
    else:
        print("  אין מספיק נתוני שעה")


# ---------------------------------------------------------------- אסטרטגיות
def strategies(X, start=5000):
    """כל אסטרטגיה מנחשת ערך אחד לכל מיקום (4 ניחושים להגרלה), רק לפי העבר."""
    N = len(X)
    rng = np.random.default_rng(0)
    res = {}

    def run(name, pick):
        hits = tot = 0
        for t in range(start, N):
            g = pick(t)
            hits += int((g == X[t]).sum()); tot += 4
        res[name] = (hits, tot)

    # ספירות מצטברות לחישוב מהיר של "חם/קר" בחלונות
    oh = np.zeros((N + 1, 4, 8), dtype=np.int32)
    for p in range(4):
        oh[1:, p, :] = np.cumsum(np.eye(8, dtype=np.int32)[X[:, p]], axis=0)

    def freq(t, w):
        return oh[t] - oh[max(0, t - w)]

    run("אקראי (בסיס השוואה)", lambda t: rng.integers(0, 8, 4))
    for w in (50, 200, 1000, 5000):
        run(f"חם: הכי נפוץ ב-{w} אחרונות", lambda t, w=w: freq(t, w).argmax(1))
        run(f"קר: הכי נדיר ב-{w} אחרונות", lambda t, w=w: freq(t, w).argmin(1))
    run("חוזר: אותו קלף כמו בהגרלה הקודמת", lambda t: X[t - 1])

    last_seen = np.zeros((4, 8), dtype=np.int64)
    gap_hits = gap_tot = 0
    for t in range(N):
        if t >= start:
            g = last_seen.argmin(1)                     # "הגיע זמנו": הכי הרבה זמן לא יצא
            gap_hits += int((g == X[t]).sum()); gap_tot += 4
        last_seen[np.arange(4), X[t]] = t
    res["\"הגיע זמנו\": הכי הרבה זמן לא יצא"] = (gap_hits, gap_tot)

    # מרקוב: לפי הערך הקודם באותו מיקום, מה הכי נפוץ שבא אחריו (חלון 5000)
    T = np.zeros((4, 8, 8), dtype=np.int32)
    m_hits = m_tot = 0
    for t in range(1, N):
        if t >= start:
            g = np.array([T[p, X[t - 1, p]].argmax() for p in range(4)])
            m_hits += int((g == X[t]).sum()); m_tot += 4
        T[np.arange(4), X[t - 1], X[t]] += 1
        if t > 5000:
            T[np.arange(4), X[t - 5001], X[t - 5000]] -= 1
    res["מרקוב: מה בא הכי הרבה אחרי הקלף הקודם"] = (m_hits, m_tot)
    return res


def main():
    rows, X = load()
    battery(rows, X)

    print(f"\n=== בדיקה קדימה של אסטרטגיות (הגרלות {5000:,} עד {len(X):,}) ===")
    print("  כל אסטרטגיה מנחשת 4 קלפים להגרלה, לפי העבר בלבד. מזל = 12.50%")
    res = strategies(X)
    k = len(res)
    for name, (h, n) in res.items():
        p = binom.sf(h - 1, n, 1 / 8)
        print(f"  {name:<44} {h:>6}/{n:<6} = {h / n * 100:6.2f}%   p={p:.3f}  (מתוקן: {min(1, p * k):.3f})")

    for fam, label in (("PP", "זוג במיקום (מזל 1.56%)"), ("SS", "קלף בודד (מזל 12.5%)")):
        wf = A.walk_forward(X, 1000, fam)
        print(f"  כורה התבניות, {label:<26} {wf['hits']:>6}/{wf['n']:<6} = {wf['rate'] * 100:6.2f}%"
              f"   p={wf['p_value']:.3f}  (בעבר הראו: {wf['avg_train_rate'] * 100:.1f}%)")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
