import pandas as pd
import streamlit as st

import core.db as db


def show():
    st.title("Stats")

    counts = db.fetch_counts()
    total = counts["total"]

    cols = st.columns(2 + len(counts["by_source"]))
    cols[0].metric("Total documents", total)
    cols[1].metric(
        "With embedding",
        f"{counts['with_embedding']} ({counts['with_embedding'] * 100 // total if total else 0}%)",
    )
    for i, (src, cnt) in enumerate(counts["by_source"]):
        cols[2 + i].metric(src, cnt)

    st.subheader("Documents collected per day (last 30 days)")
    daily = db.fetch_daily_counts(days=30)
    if daily:
        df_daily = pd.DataFrame(daily, columns=["day", "source", "count"])
        df_pivot = df_daily.pivot(index="day", columns="source", values="count").fillna(0)
        st.bar_chart(df_pivot)

    st.subheader("Top arxiv categories")
    cats = db.fetch_arxiv_categories(limit=20)
    if cats:
        df_cats = pd.DataFrame(cats, columns=["category", "count"])
        st.bar_chart(df_cats.set_index("category"))
