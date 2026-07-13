"""
Ouedkniss Job Scraper — Streamlit interface
============================================
Click "Run scrape" to fetch job listings from Ouedkniss and download the
results as CSV. Runs entirely in memory — nothing is written to disk.
"""

import collections
import csv
import datetime
import io
import time

import altair as alt
import pandas as pd
import requests
import streamlit as st

from jobs import fetch_page, parse_jobs, get_total_pages, flatten_dict

st.set_page_config(page_title="Ouedkniss Job Scraper", page_icon="🐍")
st.title("🐍 Ouedkniss Job Scraper")
st.write("Scrapes job listings from Ouedkniss's GraphQL API and lets you download the results as CSV.")

st.subheader("Filters")
use_date_filter = st.checkbox("Filter by posting date range")
from_date = to_date = None
if use_date_filter:
    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input("From", value=datetime.date.today() - datetime.timedelta(days=30))
    with col2:
        to_date = st.date_input("To", value=datetime.date.today())
    if from_date > to_date:
        st.warning("'From' date is after 'To' date — no jobs will match.")

max_pages = st.number_input(
    "Max pages to scan (48 jobs per page)",
    min_value=1,
    max_value=600,
    value=10,
    step=1,
    help="Safety cap on how many pages to fetch. Listings are sorted newest-first, so if "
         "a date range is set above, scraping also stops automatically as soon as it reaches "
         "listings older than the 'From' date — usually well before this cap is reached.",
)

if st.button("▶ Run scrape", type="primary"):
    all_jobs = []
    progress = st.progress(0.0, text="Starting...")
    status = st.empty()

    from_iso = from_date.isoformat() if from_date else None
    to_iso = to_date.isoformat() if to_date else None

    def in_range(job):
        d = job.get("created_at")
        if not d:
            return True  # keep jobs with an unknown date rather than silently dropping them
        if from_iso and d < from_iso:
            return False
        if to_iso and d > to_iso:
            return False
        return True

    def past_range(job):
        """True once a job is older than the 'From' date (listings are sorted newest-first)."""
        d = job.get("created_at")
        return bool(from_iso and d and d < from_iso)

    try:
        with requests.Session() as session:
            data = fetch_page(1, session)
            total_pages = get_total_pages(data)
            pages_to_scrape = min(max_pages, total_pages)

            for page_num in range(1, pages_to_scrape + 1):
                if page_num > 1:
                    time.sleep(1.0)
                    data = fetch_page(page_num, session)

                jobs = parse_jobs(data, page_num)
                stop_early = False
                for job in jobs:
                    if past_range(job):
                        stop_early = True
                        break
                    if in_range(job):
                        all_jobs.append(job)

                progress.progress(
                    page_num / pages_to_scrape,
                    text=f"Page {page_num}/{pages_to_scrape} — {len(all_jobs)} matching jobs",
                )

                if stop_early:
                    status.info(f"Reached listings older than {from_iso} — stopped early at page {page_num}.")
                    break

        if not stop_early:
            status.success(f"✅ Scraped {len(all_jobs)} jobs from {pages_to_scrape} pages.")

        if not all_jobs:
            st.warning("No jobs matched.")
        else:
            rows = [flatten_dict(job) for job in all_jobs]
            fieldnames = list(dict.fromkeys(key for row in rows for key in row))
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            csv_bytes = buf.getvalue().encode("utf-8-sig")

            st.download_button(
                "⬇ Download jobs.csv",
                data=csv_bytes,
                file_name="jobs.csv",
                mime="text/csv",
            )

            st.subheader("Statistics")
            st.metric("Total jobs", len(all_jobs))

            category_counts = collections.Counter(
                job.get("category_name") or "Unknown" for job in all_jobs
            )
            counts_df = pd.DataFrame(category_counts.most_common(), columns=["category", "count"])

            bars = alt.Chart(counts_df).mark_bar().encode(
                x=alt.X("count:Q", title="Jobs"),
                y=alt.Y("category:N", sort="-x", title=None),
            )
            labels = bars.mark_text(align="left", dx=3).encode(text="count:Q")
            st.altair_chart(
                (bars + labels).properties(height=25 * len(counts_df)),
                use_container_width=True,
            )

    except requests.exceptions.JSONDecodeError:
        progress.empty()
        status.error(
            "❌ Ouedkniss returned an empty, non-JSON response. This usually means it's "
            "silently blocking requests from this server's IP address — a known issue when "
            "running from cloud/datacenter hosts (we hit the exact same wall with GitHub "
            "Actions). If this is happening on a hosted deployment, try running the app "
            "locally instead: `streamlit run streamlit_app.py`."
        )
    except Exception as e:
        progress.empty()
        status.error(f"❌ Scrape failed: {e}")
