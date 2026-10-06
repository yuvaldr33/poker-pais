"""בניית דף HTML מתוצאות הניתוח."""
import html
import math

from scipy.stats import binom

from analysis import POS_NAME, VALUES

POS_LABEL = ["♠ עלה", "♥ לב", "♦ יהלום", "♣ תלתן"]


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


def esc(s):
    return html.escape(str(s))


def cards_slots(target_cards):
    slot = {p: VALUES[v] for p, v in target_cards}
    cells = []
    for p in range(4):
        v = slot.get(p)
        red = " red" if p in (1, 2) else ""
        cells.append(f'<div class="card{" on" if v else ""}{red}"><span class="suit">{POS_NAME[p]}</span>'
                     f'<span class="val">{esc(v) if v else "–"}</span></div>')
    return f'<div class="cards">{"".join(cells)}</div>'


def last_draw_slots(d):
    from analysis import SUITS
    return cards_slots([(i, VALUES.index(d[s])) for i, s in enumerate(SUITS)])


def chart_svg(cum_hits, base, w=640, h=260):
    """פגיעות מצטברות של המערכת מול מה שמצפים ממזל בלבד (עם טווח 95%)."""
    n = len(cum_hits)
    if not n:
        return ""
    xs = list(range(1, n + 1))
    lo = [binom.ppf(0.025, k, base) for k in xs]
    hi = [binom.ppf(0.975, k, base) for k in xs]
    ymax = max(max(cum_hits), max(hi)) * 1.08 + 1
    pl, pr, pt, pb = 44, 12, 12, 30

    def X(i):
        return pl + (i / n) * (w - pl - pr)

    def Y(v):
        return h - pb - (v / ymax) * (h - pt - pb)

    step = max(1, n // 300)
    idx = list(range(0, n, step)) + [n - 1]
    band = " ".join(f"{X(i):.1f},{Y(hi[i]):.1f}" for i in idx) + " " + \
           " ".join(f"{X(i):.1f},{Y(lo[i]):.1f}" for i in reversed(idx))
    exp_line = f"{X(0):.1f},{Y(0):.1f} {X(n - 1):.1f},{Y(n * base):.1f}"
    real = " ".join(f"{X(i):.1f},{Y(cum_hits[i]):.1f}" for i in idx)
    ticks = []
    for k in range(5):
        v = ymax * k / 4
        ticks.append(f'<line x1="{pl}" x2="{w - pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                     f'<text x="{pl - 6}" y="{Y(v) + 4:.1f}" class="tick" text-anchor="end">{v:.0f}</text>')
    for k in range(5):
        i = int((n - 1) * k / 4)
        ticks.append(f'<text x="{X(i):.1f}" y="{h - 10}" class="tick" text-anchor="middle">{i + 1}</text>')
    return f"""<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="פגיעות מצטברות מול מזל">
  {''.join(ticks)}
  <polygon points="{band}" class="band"/>
  <polyline points="{exp_line}" class="exp"/>
  <polyline points="{real}" class="real"/>
</svg>
<div class="legend"><span><i class="sw real"></i>פגיעות של המערכת</span>
<span><i class="sw exp"></i>מה שמזל בלבד היה נותן</span><span><i class="sw band"></i>טווח מזל רגיל (95%)</span></div>"""


def verdict(wf):
    if wf["n"] == 0:
        return "neutral", "אין מספיק נתונים"
    if wf["p_value"] < 0.01:
        return "good", "נמצא יתרון מעבר למזל"
    return "bad", "לא נמצא יתרון מעבר למזל"


def build(ctx):
    last = ctx["last"]
    wf_pp, wf_ss = ctx["wf_pp"], ctx["wf_ss"]
    cls, vtext = verdict(wf_pp)

    fc_rows = []
    for f in ctx["forecast_pp"][:5]:
        fc_rows.append(f"""<div class="fc">
  {cards_slots(f["target_cards"])}
  <div class="fc-meta">
    <div>תנאי: <b>{esc(f["cond"])}</b> לפני {f["lag"]} הגרלות {f'<span class="tag">{esc(f["tag"])}</span>' if f["tag"] else ""}</div>
    <div>בעבר (חלון של {ctx["window"]}): {f["hits"]} מתוך {f["n"]} = <b>{pct(f["rate"])}</b>
    · סיכוי אקראי {pct(f["base"])}</div>
  </div>
</div>""")
    fc_single = []
    for f in ctx["forecast_ss"][:4]:
        fc_single.append(f'<li><b>{esc(f["target"])}</b> · בעבר {f["hits"]}/{f["n"]} = {pct(f["rate"])} '
                         f'(אקראי 12.5%)</li>')

    rule_rows = []
    for r in ctx["top_rules"]:
        rule_rows.append(f"""<tr><td>{esc(r["cond"])}</td><td>{esc(r["target"])}</td><td>{r["lag"]}</td>
<td>{esc(r["tag"])}</td><td class="num">{r["hits"]}/{r["n"]} <small>({pct(r["rate"])})</small></td>
<td class="num">{r["test_hits"]}/{r["test_n"]}</td><td class="num">{r["past_hits"]}/{r["past_n"]}</td></tr>""")

    tt = ctx["top_totals"]
    perm = ctx["perm"]

    custom_rows = []
    for c in ctx["custom"]:
        if "error" in c:
            custom_rows.append(f'<tr><td colspan="6">{esc(c["text"])} · <b>שגיאה:</b> {esc(c["error"])}</td></tr>')
            continue
        (n1, h1), (n2, h2) = c["first_half"], c["second_half"]
        good = c["p"] < 0.01 and h1 / max(n1, 1) > c["base"] * 1.5 and h2 / max(n2, 1) > c["base"] * 1.5
        custom_rows.append(f"""<tr><td>{esc(c["cond"])} → {esc(c["target"])} <small>(לפני {c["lag"]})</small></td>
<td class="num">{c["hits"]}/{c["n"]} <small>({pct(c["rate"])})</small></td><td class="num">{pct(c["base"], 2)}</td>
<td class="num">{h1}/{n1}</td><td class="num">{h2}/{n2}</td>
<td>{"✅ נראה אמיתי" if good else "❌ בטווח המזל"}</td></tr>""")

    return f"""<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>מנתח צ'אנס</title>
<style>
:root{{--bg:#f6f5f2;--panel:#fff;--ink:#1d1d1f;--mute:#6b6b70;--line:#e3e1dc;--accent:#2f5bd3;
--good:#1f8a4c;--bad:#c0392b;--red:#c62828;--band:rgba(120,120,130,.18);--card:#fafafa}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#141416;--panel:#1d1d21;--ink:#ececef;
--mute:#9a9aa3;--line:#2e2e34;--accent:#7c9dff;--good:#4cc27e;--bad:#ff6b5e;--red:#ff6b6b;--band:rgba(200,200,210,.14);--card:#26262b}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.55 system-ui,"Segoe UI",Arial,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:28px;margin:0 0 4px}} h2{{font-size:20px;margin:0 0 12px}}
.sub{{color:var(--mute);margin:0 0 20px}}
section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;margin:16px 0}}
.cards{{display:flex;gap:8px;direction:ltr}}
.card{{width:58px;height:78px;border:1px solid var(--line);border-radius:9px;background:var(--card);
display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--mute)}}
.card.on{{color:var(--ink);border-color:var(--accent);border-width:2px}} .card.red .suit{{color:var(--red)}}
.card .val{{font-size:24px;font-weight:700}} .card .suit{{font-size:15px}}
.fc{{display:flex;gap:18px;align-items:center;flex-wrap:wrap;padding:12px 0;border-top:1px solid var(--line)}}
.fc:first-of-type{{border-top:0}} .fc-meta{{color:var(--mute);font-size:14px}} .fc-meta b{{color:var(--ink)}}
.tag{{display:inline-block;font-size:12px;padding:1px 8px;border-radius:99px;background:var(--bg);border:1px solid var(--line);margin-inline-start:6px}}
.verdict{{font-size:22px;font-weight:700}} .verdict.good{{color:var(--good)}} .verdict.bad{{color:var(--bad)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:14px 0}}
.stat{{border:1px solid var(--line);border-radius:10px;padding:12px}} .stat .k{{color:var(--mute);font-size:13px}}
.stat .v{{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}}
.chart{{width:100%;height:auto;direction:ltr}} .grid{{stroke:var(--line)}} .tick{{fill:var(--mute);font-size:11px}}
.band{{fill:var(--band);stroke:none}} .exp{{fill:none;stroke:var(--mute);stroke-dasharray:5 4;stroke-width:1.5}}
.real{{fill:none;stroke:var(--accent);stroke-width:2.2}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--mute)}}
.sw{{display:inline-block;width:14px;height:10px;border-radius:2px;margin-inline-end:6px;vertical-align:middle}}
.sw.real{{background:var(--accent)}} .sw.exp{{border-top:2px dashed var(--mute);height:0}} .sw.band{{background:var(--band)}}
.tbl{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
th{{color:var(--mute);font-weight:600}} .num{{font-variant-numeric:tabular-nums;direction:ltr;text-align:right}}
small{{color:var(--mute)}} .note{{color:var(--mute);font-size:14px}} code{{background:var(--bg);padding:1px 5px;border-radius:4px}}
ul{{margin:6px 0;padding-inline-start:20px}}
</style></head><body><main>
<h1>מנתח צ'אנס שיטתי</h1>
<p class="sub">עודכן לפי {ctx["n_draws"]} הגרלות (#{ctx["first_draw"]}–#{last["draw"]}). הגרלה אחרונה: #{last["draw"]}, {esc(last["date"])} {esc(last["time"])}</p>

<section>
<h2>ההגרלה האחרונה</h2>
{last_draw_slots(last)}
</section>

<section>
<h2>תחזית להגרלה #{last["draw"] + 1}: זוגות קלפים במיקום</h2>
<p class="note">אלה התבניות החזקות ביותר שחלות על ההגרלות האחרונות, לפי {ctx["window"]} ההגרלות האחרונות.
<b>שימו לב:</b> בבדיקה האמיתית למטה, הבחירה הראשונה של המערכת פגעה ב-{pct(wf_pp["rate"])} מהפעמים, מול {pct(wf_pp["base"])} במזל בלבד.</p>
{''.join(fc_rows) or '<p>אין תבנית עם מספיק הופעות.</p>'}
<h3 style="font-size:16px;margin:16px 0 4px">קלף בודד: התבניות החזקות</h3>
<ul>{''.join(fc_single)}</ul>
</section>

<section>
<h2>האם יש יתרון? הבדיקה הכנה</h2>
<div class="verdict {cls}">{vtext}</div>
<p class="note">סימולציה של שימוש יומי: לכל אחת מ-{wf_pp["n"]} ההגרלות, המערכת למדה רק מ-{ctx["window"]} ההגרלות שלפניה,
בחרה את הזוג הכי "חזק" ובדקה אם פגעה. אף הגרלה לא נבדקה על נתונים שהמערכת כבר ראתה.</p>
<div class="stats">
 <div class="stat"><div class="k">זוג במיקום: פגיעות בפועל</div><div class="v">{wf_pp["hits"]} / {wf_pp["n"]}</div><small>{pct(wf_pp["rate"], 2)}</small></div>
 <div class="stat"><div class="k">זוג במיקום: מה שמזל בלבד נותן</div><div class="v">{wf_pp["expected"]:.1f}</div><small>{pct(wf_pp["base"], 2)}</small></div>
 <div class="stat"><div class="k">אחוז "ההצלחה" שהתבניות הראו בעבר</div><div class="v">{pct(wf_pp["avg_train_rate"])}</div><small>זה מה שגורם להן להיראות משכנעות</small></div>
 <div class="stat"><div class="k">קלף בודד: פגיעות מול מזל</div><div class="v">{pct(wf_ss["rate"])}</div><small>מזל: {pct(wf_ss["base"])} · p={wf_ss["p_value"]:.2f}</small></div>
</div>
{chart_svg(wf_pp["cum_hits"], wf_pp["base"])}
<p class="note">אם הקו הכחול נשאר בתוך הרצועה האפורה, התוצאה לא שונה ממזל. p-value = {wf_pp["p_value"]:.3f}
(מתחת ל-0.01 היה מעיד על יתרון אמיתי).</p>
</section>

<section>
<h2>התבניות ה"חזקות" ביותר שנמצאו</h2>
<p class="note">נמצאו על הגרלות #{ctx["train_range"][0]}–#{ctx["train_range"][1]} ({ctx["n_rules"]:,} כללים נבדקו). אחר כך נבדקו על
{ctx["test_n_draws"]} ההגרלות האחרונות (<b>מבחן</b>) ועל {ctx["past_n_draws"]} ההגרלות שלפני כן (<b>עבר</b>), שהמנוע לא ראה בזמן החיפוש.</p>
<div class="tbl"><table>
<tr><th>אם יצא</th><th>אז יצא</th><th>אחרי</th><th>סוג</th><th>בחיפוש</th><th>במבחן</th><th>בעבר</th></tr>
{''.join(rule_rows)}
</table></div>
<p class="note">סה"כ ב-{len(ctx["top_rules"])} הכללים: במבחן {tt["test_hits"]} פגיעות מתוך {tt["test_n"]} (מזל: {tt["test_exp"]:.1f}),
בעבר {tt["past_hits"]} מתוך {tt["past_n"]} (מזל: {tt["past_exp"]:.1f}).
אחרי תיקון להשוואות מרובות, {ctx["n_significant"]} כללים נשארו מובהקים.</p>
</section>

<section>
<h2>בדיקת ערבוב: האם "תבניות" נוצרות גם מרעש?</h2>
<p class="note">ערבבנו את סדר ההגרלות {perm["rounds"]} פעמים, כך שלא נשאר שום קשר בין הגרלה להגרלה שאחריה, וחיפשנו תבניות שוב.</p>
<div class="stats">
 <div class="stat"><div class="k">התבנית הכי חזקה בנתונים האמיתיים</div><div class="v">פי {perm["real_best_lift"]:.0f}</div><small>מהסיכוי האקראי</small></div>
 <div class="stat"><div class="k">התבנית הכי חזקה בנתונים מעורבבים (חציון)</div><div class="v">פי {perm["null_best_lift_median"]:.0f}</div><small>רעש טהור</small></div>
 <div class="stat"><div class="k">כללים "חזקים מאוד" (p&lt;0.001): אמיתי מול מעורבב</div><div class="v">{perm["real_strong"]} / {perm["null_strong_median"]:.0f}</div><small>{pct(perm["frac_null_more_strong"], 0)} מהערבובים נתנו לפחות כמות כזו</small></div>
</div>
<p class="note">אם גם ברעש מעורבב יוצאות תבניות "חזקות" באותה מידה, התבניות שנמצאו הן תוצר של חיפוש בהרבה אפשרויות, ולא של חוקיות בהגרלה.</p>
</section>

<section>
<h2>הכללים של החבר</h2>
<p class="note">הוסיפו כללים לקובץ <code>my_rules.txt</code>, שורה לכל כלל, למשל <code>♠=A ♥=Q -&gt; ♠=Q ♥=A</code>
(אפשר גם <code>s h d c</code> או <code>עלה לב יהלום תלתן</code>, ו-<code>lag=2</code> להגרלה שאחרי הבאה).
כל כלל נבדק על כל {ctx["n_draws"]} ההגרלות, ובנפרד על החצי הראשון ועל החצי השני. כלל אמיתי צריך לעבוד בשני החצאים.</p>
<div class="tbl"><table>
<tr><th>כלל</th><th>פגיעות</th><th>מזל</th><th>חצי ראשון</th><th>חצי שני</th><th>מסקנה</th></tr>
{''.join(custom_rows) or '<tr><td colspan="6">אין כללים בקובץ.</td></tr>'}
</table></div>
</section>

<p class="note">ההגרלות במפעל הפיס הן אקראיות ובלתי תלויות. הכלי נבנה בשביל הכיף ובשביל בדיקה כנה, לא כהמלצה להמר.</p>
</main></body></html>"""
