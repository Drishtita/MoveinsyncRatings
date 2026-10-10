import json, pathlib
import pandas as pd
import streamlit as st
from monitor import classify, APP_FIXABLE, LOW

ROOT = pathlib.Path(__file__).parent
st.set_page_config(page_title="MoveInSync Play Store ratings", layout="wide")


@st.cache_data
def load():
    df = pd.read_csv(ROOT / "data" / "reviews.csv", parse_dates=["at", "repliedAt"])
    meta = json.loads((ROOT / "data" / "meta.json").read_text())
    return df, meta


df, meta = load()
now = df["at"].max()
hist = meta["histogram"]

st.title("How are our Play Store ratings?")
st.caption(f"MoveInSync employee app ({meta['app_id']}) · data to {now:%d %b %Y} · "
           f"{len(df):,} written reviews, last 18 months")

r90 = df[df["at"] >= now - pd.Timedelta(days=90)]
p90 = df[(df["at"] < now - pd.Timedelta(days=90)) & (df["at"] >= now - pd.Timedelta(days=180))]
c = st.columns(4)
c[0].metric("Displayed score", f"{meta['score']:.2f}", f"{meta['ratings']:,} ratings", delta_color="off")
c[1].metric("Lifetime 1-star share", f"{hist[0]/sum(hist)*100:.1f}%")
c[2].metric("Written reviews, 90-day avg", f"{r90.score.mean():.2f}",
            f"{r90.score.mean()-p90.score.mean():+.2f} vs prior 90 days")
c[3].metric("1-star share, 90 days", f"{(r90.score==1).mean()*100:.1f}%",
            f"{((r90.score==1).mean()-(p90.score==1).mean())*100:+.1f} pts", delta_color="inverse")

st.subheader("Trend: flat for 18 months, so this is chronic, not one bad release")
m = df.assign(month=df["at"].dt.to_period("M").dt.to_timestamp()).groupby("month").agg(
    avg_stars=("score", "mean"), one_star_pct=("score", lambda s: (s == 1).mean() * 100),
    reviews=("score", "size"))
a, b = st.columns(2)
a.line_chart(m["avg_stars"], y_label="Average stars (written reviews)")
b.line_chart(m["one_star_pct"], y_label="1-star share (%)")

low = df[df.score <= LOW].copy()
low["theme"] = low.content.apply(classify)
low["owner"] = low.theme.map(lambda t: "App" if t in APP_FIXABLE else "Ops / unclear")
st.subheader(f"Why people give 1-2 stars (n={len(low):,})")
window = st.radio("Period", ["All 18 months", "Last 90 days"], horizontal=True)
sub = low if window == "All 18 months" else low[low["at"] >= now - pd.Timedelta(days=90)]
t = sub.theme.value_counts().rename("reviews").to_frame()
t["share_%"] = (t.reviews / len(sub) * 100).round(1)
t["owner"] = [("App" if k in APP_FIXABLE else "Ops / unclear") for k in t.index]
l, r = st.columns([3, 2])
l.bar_chart(t["reviews"], horizontal=True)
r.dataframe(t, width="stretch")
st.caption(f"App-owned: {(sub.owner=='App').mean()*100:.0f}% of low-star reviews. "
           "Keyword tagging, ~75% agreement on a 45-review hand check; "
           "'Crash/slow' is probably overstated.")

st.subheader("App versions with the highest low-star share (n ≥ 40)")
g = df.groupby("reviewCreatedVersion").score.agg(reviews="size", avg_stars="mean")
g["low_star_%"] = (df[df.score <= LOW].groupby("reviewCreatedVersion").size() / g.reviews * 100).fillna(0)
st.dataframe(g[g.reviews >= 40].sort_values("low_star_%", ascending=False).head(8).round(2),
             width="stretch")

st.subheader("Developer replies")
rep = df.replyContent.notna()
c = st.columns(3)
c[0].metric("Reply rate, all reviews", f"{rep.mean()*100:.1f}%")
c[1].metric("Reply rate, 1-2 star", f"{df[df.score<=LOW].replyContent.notna().mean()*100:.1f}%")
c[2].metric("Replies sent to 4-5 star", f"{(df[rep].score>=4).mean()*100:.0f}%")

st.subheader("Reply to these first: top unanswered low-star reviews")
un = low[low.replyContent.isna()].sort_values(["thumbsUpCount", "at"], ascending=False).head(15)
st.dataframe(un[["at", "score", "reviewCreatedVersion", "thumbsUpCount", "theme", "content"]]
             .rename(columns={"reviewCreatedVersion": "version", "thumbsUpCount": "upvotes"}),
             width="stretch", hide_index=True)

with st.expander("Refresh data from Google Play (may be slow or blocked on cloud hosts)"):
    if st.button("Scrape latest reviews"):
        try:
            from monitor import load_live
            new, score, h, n = load_live()
            new.to_csv(ROOT / "data" / "reviews.csv", index=False)
            (ROOT / "data" / "meta.json").write_text(json.dumps(
                {**meta, "score": score, "histogram": h, "ratings": n,
                 "scraped_on": str(pd.Timestamp.now().date())}))
            st.cache_data.clear()
            st.success(f"Saved {len(new):,} reviews. Reload the page.")
        except Exception as e:
            st.error(f"Scrape failed, still showing saved data: {e}")
