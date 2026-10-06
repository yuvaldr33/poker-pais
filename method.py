"""השיטה של החבר: כאן נכנסת הלוגיקה של התחזית.

כרגע זו שיטת דמו בלבד (DEMO = True), כדי שהאפליקציה תעבוד מקצה לקצה.
כשהשיטה האמיתית תהיה מוכנה, מחליפים את הפונקציה predict ומשנים DEMO ל-False.

predict מקבל:
    history: רשימת הגרלות מהישנה לחדשה. כל הגרלה היא dict:
             {"draw": 53690, "date": "06/10/26", "time": "21:00",
              "spade": "7", "heart": "A", "diamond": "8", "club": "10"}
    next_draw: מספר ההגרלה שעליה מנחשים.
ומחזיר dict:
    {"cards": {"spade": "A", "heart": None, "diamond": "Q", "club": None},  # None = לא מנחשים
     "reason": "הסבר קצר שיוצג באפליקציה"}
"""
import random

NAME = "שיטת דמו"
DESCRIPTION = "תחזית לדוגמה בלבד, עד שתוכנס השיטה של החבר."
DEMO = True

VALUES = ["7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["spade", "heart", "diamond", "club"]


def predict(history, next_draw):
    rng = random.Random(next_draw)              # קבוע לכל הגרלה, כדי שהתחזית לא תשתנה ברענון
    chosen = rng.sample(SUITS, 2)
    cards = {s: (rng.choice(VALUES) if s in chosen else None) for s in SUITS}
    return {"cards": cards, "reason": "דמו: קלפים לדוגמה, לא שיטה אמיתית"}
