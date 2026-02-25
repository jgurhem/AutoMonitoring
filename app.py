import io
import logging
import re
import sys
import textwrap
from datetime import datetime, timedelta, timezone

from streamlit_js_eval import streamlit_js_eval

import pandas as pd
import streamlit as st

import db

st.set_page_config(page_title="Monitoring", layout="wide", page_icon="📡")

page = st.sidebar.radio("Navigation", ["Browse", "Stats", "Semantic Search", "Processing"])

_screen_width = streamlit_js_eval(js_expressions="window.innerWidth", key="screen_width")
# sidebar (~240px) + padding (~64px), ~7.5px per monospace char
wrap_width = max(80, int((_screen_width - 304) / 7.5)) if _screen_width else 120


# ─── helpers ────────────────────────────────────────────────────────────────

def capture_run(fn):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        fn()
    except Exception as e:
        buf.write(f"\nERROR: {e}\n")
    finally:
        root.removeHandler(handler)
    return buf.getvalue()


def show_document(doc_id):
    d = db.fetch_document(doc_id)
    if not d:
        return
    title, authors, url, description, content, categories, published_at = d
    st.divider()
    st.subheader(title)
    meta = []
    if url:
        meta.append(f"[Open]({url})")
    if published_at:
        meta.append(str(published_at)[:10])
    if categories:
        meta.append(" | ".join(categories))
    st.write("  •  ".join(meta))
    if authors:
        st.write("**Authors:** " + ", ".join(authors))
    st.write(description or "")
    with st.expander("Full content"):
        st.write(content or "")


# ─── Browse ─────────────────────────────────────────────────────────────────

if page == "Browse":
    st.title("Browse")

    c1, c2, c3, c4 = st.columns(4)
    source = c1.selectbox("Source", ["all", "rss", "arxiv", "github"])
    days = c2.number_input("Collected last N days", min_value=1, max_value=365, value=30)
    emb = c3.selectbox("Embedding", ["all", "yes", "no"])
    search = c4.text_input("Search title")

    has_embedding = True if emb == "yes" else (False if emb == "no" else None)
    rows = db.fetch_documents(
        since=datetime.now(timezone.utc) - timedelta(days=int(days)),
        source=source if source != "all" else None,
        has_embedding=has_embedding,
        search=search or None,
    )

    df = pd.DataFrame(rows, columns=["id", "source", "title", "published_at", "url", "has_emb"])
    st.caption(f"{len(df)} documents")

    sel = st.dataframe(
        df[["source", "title", "published_at", "has_emb"]],
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
    )

    if sel.selection.rows:
        show_document(df.iloc[sel.selection.rows[0]]["id"])


# ─── Stats ───────────────────────────────────────────────────────────────────

elif page == "Stats":
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


# ─── Semantic Search ─────────────────────────────────────────────────────────

elif page == "Semantic Search":
    st.title("Semantic Search")

    @st.cache_resource
    def load_embedder():
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    query = st.text_input("Query")
    top_k = st.slider("Results", 5, 50, 10)

    if query:
        with st.spinner("Searching..."):
            vec = load_embedder().embed_query(query)
            rows = db.search_similar(vec, top_k=top_k)

        df = pd.DataFrame(rows, columns=["id", "source", "title", "url", "published_at", "similarity"])
        df["similarity"] = df["similarity"].round(4)

        sel = st.dataframe(
            df[["similarity", "source", "title", "published_at"]],
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
        )

        if sel.selection.rows:
            show_document(df.iloc[sel.selection.rows[0]]["id"])


# ─── Processing ───────────────────────────────────────────────────────────────

elif page == "Processing":
    st.title("Processing")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Deduplicate")
        st.write("Find near-duplicate documents using cosine similarity.")
        if st.button("Run dedup"):
            with st.spinner("Finding duplicates..."):
                from dedup import main as dedup_main
                st.session_state["proc_output"] = capture_run(dedup_main)

    with col2:
        st.subheader("Novelty")
        st.write("Score documents by how different they are from the rest.")
        if st.button("Run novelty"):
            with st.spinner("Computing novelty scores..."):
                from novelty import main as novelty_main
                st.session_state["proc_output"] = capture_run(novelty_main)

    with col3:
        st.subheader("Cluster")
        st.write("Group documents into topic clusters using HDBSCAN.")
        new_only = st.checkbox("Show only new articles")
        if st.button("Run cluster"):
            with st.spinner("Clustering..."):
                from cluster import main as cluster_main
                old_argv = sys.argv
                sys.argv = ["cluster"] + (["--new"] if new_only else [])
                try:
                    st.session_state["proc_output"] = capture_run(cluster_main)
                finally:
                    sys.argv = old_argv

    if "proc_output" in st.session_state:
        st.divider()
        clean = re.sub(r"\033\[[0-9;]*m", "", st.session_state["proc_output"] or "Done.")
        wrapped = "\n".join(
            textwrap.fill(line, width=wrap_width, subsequent_indent="", break_long_words=True)
            if len(line) > wrap_width else line
            for line in clean.splitlines()
        )
        st.code(wrapped)
