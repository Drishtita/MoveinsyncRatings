"""MoveInSync Play Store rating monitor.

Answers "How are our Play Store ratings?" in one run.
LIVE mode (Colab): scrapes Play Store.  OFFLINE mode: pass a reviews.csv.
"""
import re, sys, datetime as dt
import pandas as pd

APP_ID = "com.moveinsync.ets"
DAYS_BACK = 548          # how far back to scrape
LOW = 2                  # <= this many stars counts as "low"

# Ordered rules: first match wins (primary theme). Keyword baseline, ~75% agreement
# with a manual read of 45 low-star reviews. Swap in llm_classify() for better accuracy.
RULES = [
    ("Safety/SOS", r"sos\b|safety|unsafe|harass|panic|female|women"),
    ("Driver/service (ops)", r"rude|abusive|unprofessional|misbehav|drunk|rash"),
    ("QR/check-in/boarding", r"\bqr\b|scan|check.?in|check.?out|boarding"),
    ("Login/OTP/session", r"otp|verification code|not receiving (the )?code|logging you|logs you|keeps logging|log(ged|ging)?[ -]?(out|off|in)\b|sign(ed|ing)?[ -]?(out|in)|logout|login|session expired"),
    ("Crash/slow/errors", r"crash|hang|slow|loading|not (open|work|respond)|won.?t (open|load|work)|something went wrong|lag|stuck|error|glitch|bug|freez|doesn.?t work|does not work"),
    ("Tracking/GPS/ETA", r"gps|track|live location|map|locat|eta\b|estimated|not updat|zoom"),
    ("Pickup timing/scheduling", r"too early|pick ?up time|pickup time|timing|schedule|early pick|wrong time|sequence|routing|route|nodal|clubb"),
    ("Booking/cancel/no-show", r"marked as|book|cancel|no.?show|waitlist|seat|allocat|roster|not assign|no cab|parking"),
    ("Forced feedback/popups", r"feedback|rate\b|rating|review|pop ?up|banner|advert|reminder|notification|mandatory"),
    ("Call/helpdesk/support", r"call|helpdesk|customer (care|support)|support|company policy|contact"),
    ("Driver/service (ops)", r"driver|late|delay|service|transport|cab"),
    ("UI/UX", r"\bui\b|\bux\b|interface|user friendly|confus|dark mode|font|design|navigation"),
]
APP_FIXABLE = {"Login/OTP/session", "Crash/slow/errors", "Tracking/GPS/ETA", "QR/check-in/boarding",
               "Forced feedback/popups", "UI/UX", "Booking/cancel/no-show", "Call/helpdesk/support"}


def classify(text):
    s = str(text).lower()
    for theme, pat in RULES:
        if re.search(pat, s):
            return theme
    return "Generic/no detail" if len(s) < 40 else "Other"


def llm_classify(texts):
    """Optional: higher-accuracy tagging with the Claude API (needs ANTHROPIC_API_KEY).
    Left as a stub on purpose so the notebook runs with zero setup."""
    raise NotImplementedError


def load_live():
    from google_play_scraper import app, reviews, Sort
    info = app(APP_ID, lang="en", country="in")
    cutoff = dt.datetime.now() - dt.timedelta(days=DAYS_BACK)
    rows, token = [], None
    while True:
        batch, token = reviews(APP_ID, lang="en", country="in", sort=Sort.NEWEST,
                               count=200, continuation_token=token)
        rows += batch
        if not batch or token is None or batch[-1]["at"] < cutoff:
            break
    df = pd.DataFrame(rows)[["content", "score", "at", "reviewCreatedVersion",
                             "thumbsUpCount", "replyContent", "repliedAt"]]
    return df, info["score"], info["histogram"], info["ratings"]


def report(df, score=None, hist=None, n_ratings=None):
    df = df.copy()
    df["at"] = pd.to_datetime(df["at"])
    now = df["at"].max()
    out = []
    p = out.append
    p(f"# Play Store rating check - {now:%d %b %Y}\n")
    if score is not None:
        p(f"Displayed score: {score:.2f} from {n_ratings:,} ratings. Histogram 1-5 star: {hist}")
        p(f"Lifetime 1-star share: {hist[0]/sum(hist)*100:.1f}%\n")
    r90 = df[df["at"] >= now - pd.Timedelta(days=90)]
    p1 = df[(df["at"] < now - pd.Timedelta(days=90)) & (df["at"] >= now - pd.Timedelta(days=180))]
    p(f"Written reviews, last 90 days: n={len(r90)}, avg {r90.score.mean():.2f}, "
      f"1-star share {(r90.score==1).mean()*100:.1f}%")
    p(f"Previous 90 days:              n={len(p1)}, avg {p1.score.mean():.2f}, "
      f"1-star share {(p1.score==1).mean()*100:.1f}%\n")

    low = df[df.score <= LOW].copy()
    low["theme"] = low.content.apply(classify)
    t = low.theme.value_counts()
    p("## Why people give 1-2 stars (all period)")
    for k, v in t.items():
        tag = "app" if k in APP_FIXABLE else "ops/other"
        p(f"- {k}: {v} ({v/len(low)*100:.0f}%) [{tag}]")
    lo90 = low[low["at"] >= now - pd.Timedelta(days=90)]
    p("\n## Top themes, last 90 days")
    for k, v in lo90.theme.value_counts().head(5).items():
        p(f"- {k}: {v} ({v/len(lo90)*100:.0f}%)")

    p("\n## Versions with enough reviews and worst low-star share (n>=40)")
    g = df.groupby("reviewCreatedVersion").score.agg(n="size", avg="mean")
    g["low%"] = (df[df.score <= LOW].groupby("reviewCreatedVersion").size() / g.n * 100).fillna(0)
    for v, r in g[g.n >= 40].sort_values("low%", ascending=False).head(5).iterrows():
        p(f"- {v}: n={int(r.n)}, avg {r.avg:.2f}, low-star {r['low%']:.0f}%")

    rep = df.replyContent.notna()
    p(f"\n## Developer replies\nReply rate overall {rep.mean()*100:.1f}%, "
      f"on 1-2 star {df[df.score<=LOW].replyContent.notna().mean()*100:.1f}%, "
      f"share of replies that went to 4-5 star {(df[rep].score>=4).mean()*100:.0f}%")

    unanswered = low[low.replyContent.isna()].sort_values("thumbsUpCount", ascending=False).head(5)
    p("\n## Top unanswered low-star reviews (reply to these first)")
    for _, r in unanswered.iterrows():
        p(f"- [{r.score}*, v{r.reviewCreatedVersion}, {r.thumbsUpCount} upvotes] {str(r.content)[:140]!r}")
    return "\n".join(out), low


if __name__ == "__main__":
    if len(sys.argv) > 1:   # offline: python monitor.py reviews.csv
        d = pd.read_csv(sys.argv[1])
        text, _ = report(d)
    else:
        d, s, h, n = load_live()
        text, _ = report(d, s, h, n)
    print(text)
