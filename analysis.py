"""מנוע חיפוש תבניות ובדיקה סטטיסטית לצ'אנס.

מושגים:
  - מיקום = עמודת סוג (♠ ♥ ♦ ♣). ערך = 7..A (8 אפשרויות, סיכוי 1/8 לכל אחד).
  - כלל = "אם בהגרלה n יש <תנאי>, אז בהגרלה n+L יש <יעד>".
  - תנאי/יעד הוא קלף בודד (מיקום+ערך) או זוג (שני מיקומים+שני ערכים).
  - סיכוי אקראי ליעד: 1/8 לקלף בודד, 1/64 לזוג.

הבדיקה הכנה: כללים נמצאים על הגרלות "למידה" ונבדקים על הגרלות שהמנוע לא ראה.
"""
from itertools import combinations

import numpy as np
from scipy.stats import binom

VALUES = ["7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["spade", "heart", "diamond", "club"]
POS_NAME = ["♠", "♥", "♦", "♣"]
PAIRS = list(combinations(range(4), 2))          # 6 זוגות מיקומים
LAGS = (1, 2, 3)
MIN_SUPPORT = 8                                  # מינימום הופעות של התנאי כדי לסמוך על כלל

# משפחות כללים: (סוג תנאי, סוג יעד)
FAMILIES = {"PP": ("P", "P"), "PS": ("P", "S"), "SS": ("S", "S"), "SP": ("S", "P")}
BASE = {"S": 1 / 8, "P": 1 / 64}
WIDTH = {"S": 32, "P": 384}
PER_DRAW = {"S": 4, "P": 6}                      # כמה תנאים/יעדים יש בכל הגרלה


def to_matrix(draws):
    return np.array([[VALUES.index(d[s]) for s in SUITS] for d in draws], dtype=np.int64)


def single_idx(X):
    """(N,4): אינדקס קלף בודד = מיקום*8+ערך."""
    return np.arange(4) * 8 + X


def pair_idx(X):
    """(N,6): אינדקס זוג = זוג_מיקומים*64 + ערך1*8 + ערך2."""
    return np.stack([q * 64 + X[:, i] * 8 + X[:, j] for q, (i, j) in enumerate(PAIRS)], axis=1)


def onehot(idx, width):
    M = np.zeros((idx.shape[0], width), dtype=np.int32)
    np.put_along_axis(M, idx, 1, axis=1)
    return M


def encodings(X):
    s, p = single_idx(X), pair_idx(X)
    return {"S": (s, onehot(s, 32)), "P": (p, onehot(p, 384))}


# ---------------------------------------------------------------- תיאור כללים
def describe(kind, idx):
    if kind == "S":
        pos, v = divmod(int(idx), 8)
        return [(pos, v)]
    q, r = divmod(int(idx), 64)
    a, b = divmod(r, 8)
    i, j = PAIRS[q]
    return [(i, a), (j, b)]


def cards_text(cards):
    return " ".join(f"{VALUES[v]}{POS_NAME[p]}" for p, v in cards)


def transform_tag(cond, target):
    """מזהה קשר "מעניין" בין התנאי ליעד (היפוך, חזרה וכו')."""
    if len(cond) != len(target):
        return ""
    cpos, cval = [c[0] for c in cond], [c[1] for c in cond]
    tpos, tval = [t[0] for t in target], [t[1] for t in target]
    if cpos == tpos and cval == tval:
        return "חזרה"
    if cpos == tpos and len(cval) == 2 and cval == tval[::-1]:
        return "היפוך צדדים"
    if sorted(cval) == sorted(tval):
        return "אותם ערכים, מיקום אחר"
    if cpos == tpos and all(abs(a - b) == 1 for a, b in zip(cval, tval)):
        return "הזזה ±1"
    return ""


# ---------------------------------------------------------------- כריית כללים
def mine(X, lags=LAGS, families=FAMILIES, min_support=MIN_SUPPORT):
    """מחזיר רשימת כללים עם סטטיסטיקה על X (הגרלות בסדר כרונולוגי)."""
    enc = encodings(X)
    rules = []
    for fam, (ck, tk) in families.items():
        for L in lags:
            C = enc[ck][1][:-L].astype(np.float64)
            T = enc[tk][1][L:].astype(np.float64)
            hits = C.T @ T                       # (תנאים, יעדים)
            n = C.sum(axis=0)[:, None] * np.ones((1, hits.shape[1]))
            p0 = BASE[tk]
            mask = n >= min_support
            ci, ti = np.nonzero(mask)
            h, nn = hits[ci, ti], n[ci, ti]
            pv = binom.sf(h - 1, nn, p0)
            for c, t, hh, n_, p in zip(ci, ti, h, nn, pv):
                rules.append({"fam": fam, "lag": L, "c": int(c), "t": int(t),
                              "n": int(n_), "hits": int(hh), "base": p0, "p": float(p)})
    return rules


def bh_qvalues(p):
    p = np.asarray(p)
    order = np.argsort(p)
    ranked = p[order] * len(p) / (np.arange(len(p)) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.minimum(q, 1)
    return out


def evaluate_rule(X, fam, lag, c, t):
    """כמה פעמים התנאי הופיע ובכמה מהן היעד הגיע, על X."""
    ck, tk = FAMILIES[fam]
    enc = encodings(X)
    C = enc[ck][1][:-lag, c] if len(X) > lag else np.zeros(0)
    T = enc[tk][1][lag:, t] if len(X) > lag else np.zeros(0)
    return int(C.sum()), int((C * T).sum())


def rule_view(r):
    ck, tk = FAMILIES[r["fam"]]
    cond, targ = describe(ck, r["c"]), describe(tk, r["t"])
    return {**r, "cond": cards_text(cond), "target": cards_text(targ),
            "tag": transform_tag(cond, targ), "rate": r["hits"] / r["n"] if r["n"] else 0,
            "lift": (r["hits"] / r["n"]) / r["base"] if r["n"] else 0}


# ---------------------------------------------------------------- בדיקת ערבוב
def best_stats(X, fam="PP", lags=LAGS, min_support=MIN_SUPPORT):
    """הכלל ה"הכי חזק" שנמצא, ומספר הכללים עם p<0.001."""
    ck, tk = FAMILIES[fam]
    enc = encodings(X)
    best_p, best_lift, strong = 1.0, 0.0, 0
    for L in lags:
        C = enc[ck][1][:-L].astype(np.float64)
        T = enc[tk][1][L:].astype(np.float64)
        hits = C.T @ T
        n = np.repeat(C.sum(axis=0)[:, None], hits.shape[1], axis=1)
        m = n >= min_support
        pv = binom.sf(hits[m] - 1, n[m], BASE[tk])
        if pv.size:
            best_p = min(best_p, pv.min())
            strong += int((pv < 0.001).sum())
            best_lift = max(best_lift, (hits[m] / n[m]).max() / BASE[tk])
    return best_p, best_lift, strong


def permutation_test(X, rounds=200, seed=7, fam="PP"):
    """מערבב את סדר ההגרלות (מוחק כל קשר בין הגרלה להגרלה הבאה) ובודק אילו
    "תבניות" נמצאות גם אז. אם התבניות האמיתיות לא חזקות מאלו, אין יתרון."""
    rng = np.random.default_rng(seed)
    real = best_stats(X, fam)
    null = [best_stats(X[rng.permutation(len(X))], fam) for _ in range(rounds)]
    null_p = np.array([x[0] for x in null])
    null_strong = np.array([x[2] for x in null])
    return {
        "real_best_p": real[0], "real_best_lift": real[1], "real_strong": real[2],
        "null_best_p_median": float(np.median(null_p)),
        "null_best_lift_median": float(np.median([x[1] for x in null])),
        "null_strong_median": float(np.median(null_strong)),
        # כמה מהערבובים נתנו כלל "הכי טוב" חזק לפחות כמו האמיתי
        "frac_null_better": float((null_p <= real[0]).mean()),
        "frac_null_more_strong": float((null_strong >= real[2]).mean()),
        "rounds": rounds,
    }


# ---------------------------------------------------------------- Walk-forward
class RollingCounts:
    """ספירות כללים על חלון מתגלגל, עם הוספה/הסרה של מעבר בודד (מהיר)."""

    def __init__(self, enc, fam, lags):
        self.ck, self.tk = FAMILIES[fam]
        self.ci, self.ti = enc[self.ck][0], enc[self.tk][0]
        self.lags = lags
        self.M = {L: np.zeros((WIDTH[self.ck], WIDTH[self.tk]), dtype=np.int32) for L in lags}

    def _apply(self, L, src, dst, sign):
        a, b = np.meshgrid(self.ci[src], self.ti[dst], indexing="ij")
        np.add.at(self.M[L], (a.ravel(), b.ravel()), sign)

    def add_draw(self, t, lo):
        """הגרלה t נכנסה לחלון שמתחיל ב-lo: מוסיף את המעברים שמסתיימים בה."""
        for L in self.lags:
            if t - L >= lo:
                self._apply(L, t - L, t, 1)

    def drop_draw(self, t, hi):
        """הגרלה t יוצאת מתחילת החלון: מסיר מעברים שמתחילים בה."""
        for L in self.lags:
            if t + L < hi:
                self._apply(L, t, t + L, -1)

    def candidates(self, cond_rows, min_support=MIN_SUPPORT):
        """כל התחזיות האפשריות כשהתנאים של הגרלות האחרונות ידועים.
        cond_rows[L] = מספר ההגרלה שמשמשת כתנאי לפיגור L."""
        out = []
        for L in self.lags:
            r = cond_rows.get(L)
            if r is None:
                continue
            for c in self.ci[r]:
                hits = self.M[L][c]
                n = hits.sum() / PER_DRAW[self.tk]
                if n < min_support:
                    continue
                pv = binom.sf(hits - 1, n, BASE[self.tk])
                for t in np.argsort(pv)[:3]:
                    out.append((float(pv[t]), L, int(c), int(t), int(hits[t]), int(n)))
        out.sort()
        return out


def walk_forward(X, window=1000, fam="PP", lags=LAGS, min_support=MIN_SUPPORT):
    """לכל הגרלה t (אחרי החלון הראשון): לומדים רק מ-window הגרלות שלפניה,
    בוחרים את התחזית הכי חזקה, ובודקים אם פגעה. זו הסימולציה הכי כנה של
    "מה היה קורה אם החבר היה משתמש במערכת כל יום"."""
    enc = encodings(X)
    rc = RollingCounts(enc, fam, lags)
    for t in range(window):
        rc.add_draw(t, 0)
    tk = FAMILIES[fam][1]
    tgt_sets = [set(row) for row in enc[tk][0]]
    log = []
    for t in range(window, len(X)):
        lo = t - window
        cands = rc.candidates({L: t - L for L in lags}, min_support)
        if cands:
            pv, L, c, tg, h, n = cands[0]
            log.append({"t": t, "hit": tg in tgt_sets[t], "p": pv, "lag": L,
                        "c": c, "tg": tg, "train_rate": h / n})
        # מזיזים את החלון: מוסיפים את t, מסירים את lo
        rc.add_draw(t, lo)
        rc.drop_draw(lo, t + 1)
    hits = sum(r["hit"] for r in log)
    n = len(log)
    base = BASE[tk]
    return {
        "fam": fam, "n": n, "hits": hits, "rate": hits / n if n else 0, "base": base,
        "expected": n * base,
        "p_value": float(binom.sf(hits - 1, n, base)) if n else 1.0,
        "cum_hits": np.cumsum([r["hit"] for r in log]).tolist(),
        "avg_train_rate": float(np.mean([r["train_rate"] for r in log])) if log else 0,
    }


def forecast(X, window=1000, fam="PP", lags=LAGS, min_support=MIN_SUPPORT, top=8):
    """תחזית להגרלה הבאה לפי window ההגרלות האחרונות."""
    Xw = X[-window:]
    enc = encodings(Xw)
    rc = RollingCounts(enc, fam, lags)
    for t in range(len(Xw)):
        rc.add_draw(t, 0)
    N = len(Xw)
    cands = rc.candidates({L: N - L for L in lags}, min_support)
    ck, tk = FAMILIES[fam]
    seen, out = set(), []
    for pv, L, c, tg, h, n in cands:
        if tg in seen:
            continue
        seen.add(tg)
        cond, targ = describe(ck, c), describe(tk, tg)
        out.append({"p": pv, "lag": L, "cond": cards_text(cond), "target": cards_text(targ),
                    "target_cards": targ, "hits": h, "n": n, "rate": h / n,
                    "base": BASE[tk], "tag": transform_tag(cond, targ)})
        if len(out) >= top:
            break
    return out


# ---------------------------------------------------------------- כללי החבר
SUIT_ALIASES = {"♠": 0, "s": 0, "spade": 0, "עלה": 0,
                "♥": 1, "h": 1, "heart": 1, "לב": 1,
                "♦": 2, "d": 2, "diamond": 2, "יהלום": 2,
                "♣": 3, "c": 3, "club": 3, "תלתן": 3}


def parse_rule(line):
    """פורמט: '♠=A ♥=Q -> ♠=Q ♥=A'  (אפשר להוסיף lag=2 בסוף)."""
    line = line.split("#")[0].strip()
    if "->" not in line:
        return None
    lag = 1
    left, right = line.split("->", 1)
    toks_r = right.split()
    for tok in list(toks_r):
        if tok.lower().startswith("lag="):
            lag = int(tok.split("=")[1])
            toks_r.remove(tok)

    def side(tokens):
        out = []
        for tok in tokens:
            k, v = tok.split("=")
            out.append((SUIT_ALIASES[k.strip().lower()], VALUES.index(v.strip().upper())))
        return out

    return {"cond": side(left.split()), "target": side(toks_r), "lag": lag, "text": line}


def evaluate_custom(X, rule):
    L = rule["lag"]
    src, dst = X[:-L], X[L:]
    cm = np.all([src[:, p] == v for p, v in rule["cond"]], axis=0)
    tm = np.all([dst[:, p] == v for p, v in rule["target"]], axis=0)
    n, h = int(cm.sum()), int((cm & tm).sum())
    base = (1 / 8) ** len(rule["target"])
    half = len(src) // 2
    n1, h1 = int(cm[:half].sum()), int((cm[:half] & tm[:half]).sum())
    n2, h2 = n - n1, h - h1
    return {"text": rule["text"], "cond": cards_text(rule["cond"]),
            "target": cards_text(rule["target"]), "lag": L, "n": n, "hits": h,
            "rate": h / n if n else 0, "base": base,
            "p": float(binom.sf(h - 1, n, base)) if n else 1.0,
            "first_half": (n1, h1), "second_half": (n2, h2)}
