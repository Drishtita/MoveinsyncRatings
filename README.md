# MoveInSync: How are our Play Store ratings?

A small, repeatable answer to the question "how are our Play Store ratings, and why?" for the MoveInSync employee app (`com.moveinsync.ets`).

- **Live dashboard:** https://moveinsyncratings-mzylackcj8jnmwvrq9kqlt.streamlit.app/
- **Decision memo:** https://drive.google.com/file/d/1mpNcj-q-TbMhZdhbrJOI0Zj0W5wj6Upy/view
- **Notebook (re-run any time):** https://drive.google.com/file/d/1OWValLhf1eYMB17xtkTxNYLJgOT6KfIR/view?usp=sharing

## Headline
The app shows 4.64 stars from 114,835 ratings, but 6.4% of all ratings are 1 star, and 25% of written reviews over the last 18 months are 1 star. The share has been flat since April 2025, so it is a standing problem, not one bad release. About 55% of low-star reviews are app-fixable (login and logouts, crashes and slowness, live tracking, forced rating popups); about 18% are cab/driver operations. Only 2.8% of reviews get a developer reply.

## What is in here
| File | Purpose |
| --- | --- |
| `app.py` | Streamlit dashboard: score, 90-day trend, 1-2 star themes, worst versions, reply rate, unanswered reviews to answer first |
| `monitor.py` | Scraper, keyword theme classifier, and text report (`python monitor.py data/reviews.csv`) |
| `data/reviews.csv` | 4,400 written reviews, 7 Apr 2025 to 9 Oct 2026 |
| `data/meta.json` | Displayed score and rating histogram on 10 Oct 2026 |
| `notebooks/` | Colab notebook that scrapes live and prints the weekly summary |

## Run it
```
pip install -r requirements.txt
streamlit run app.py
```

## Method and limits
- Reviews scraped with `google-play-scraper` (India store). Each 1-2 star review gets one primary theme from ordered keyword rules built around the commute journey. About 75% agreement on a hand check of 45 reviews; "Crash/slow" is probably overstated and 27% of low-star reviews have no usable detail.
- Written reviews skew negative, so they explain why people complain; they are not the score itself.
- Next steps: scheduled weekly run, model-based tagging, validation with a customer transport desk.
