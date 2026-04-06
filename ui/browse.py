from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

import core.db as db
from ui._document import show_document

PAGE_SIZE = 50


def show(user):
    st.title("Browse")

    c1, c2, c3 = st.columns(3)
    source = c1.selectbox("Source", ["all", "rss", "arxiv", "github"])
    days = c2.number_input("Collected last N days", min_value=1, max_value=365, value=30)
    search = c3.text_input("Search title")

    # Reset page when filters change
    filter_key = (source, int(days), search)
    if st.session_state.get("browse_filter") != filter_key:
        st.session_state["browse_page"] = 0
        st.session_state["browse_filter"] = filter_key

    page_idx = st.session_state.get("browse_page", 0)
    since = datetime.now(timezone.utc) - timedelta(days=int(days))
    source_filter = source if source != "all" else None

    total = db.count_documents_for_user(
        user_id=user["id"],
        since=since,
        source=source_filter,
        search=search or None,
    )
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page_idx = min(page_idx, total_pages - 1)

    rows = db.fetch_documents_for_user(
        user_id=user["id"],
        since=since,
        source=source_filter,
        search=search or None,
        limit=PAGE_SIZE,
        offset=page_idx * PAGE_SIZE,
    )

    df = pd.DataFrame(rows, columns=["id", "source", "title", "published_at", "url", "read_at"])
    df["read"] = df["read_at"].apply(lambda x: "✓" if pd.notna(x) else "")
    unread = int(df["read_at"].isna().sum())

    cap_col, markall_col = st.columns([5, 1])
    cap_col.caption(f"{total} documents ({unread} unread on this page)")
    if markall_col.button("Mark all read"):
        db.mark_all_read_for_user(user["id"], since, source_filter, search or None)
        st.rerun()

    sel = st.dataframe(
        df[["read", "source", "title", "published_at"]],
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
    )

    col_prev, col_info, col_next = st.columns([1, 2, 1])
    if col_prev.button("← Prev", disabled=page_idx == 0):
        st.session_state["browse_page"] = page_idx - 1
        st.rerun()
    col_info.markdown(f"Page **{page_idx + 1}** of **{total_pages}**")
    if col_next.button("Next →", disabled=page_idx >= total_pages - 1):
        st.session_state["browse_page"] = page_idx + 1
        st.rerun()

    if sel.selection.rows:
        show_document(user, df.iloc[sel.selection.rows[0]]["id"])
