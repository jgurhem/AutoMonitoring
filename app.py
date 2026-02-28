import argparse
import io
import logging
import re
import textwrap
from datetime import datetime, timedelta, timezone

from streamlit_js_eval import streamlit_js_eval

import pandas as pd
import streamlit as st

import core.db as db
from core.auth import current_user

st.set_page_config(page_title="Monitoring", layout="wide", page_icon="📡")

# ─── Auth gate ───────────────────────────────────────────────────────────────

if "user" not in st.session_state:
    from ui.login import show as show_login
    show_login()
    st.stop()

user = current_user()

# ─── Sidebar / navigation ─────────────────────────────────────────────────────

_arg_parser = argparse.ArgumentParser(add_help=False)
_arg_parser.add_argument("--model", default="mixtral")
_args, _ = _arg_parser.parse_known_args()
ollama_model = _args.model

nav_pages = ["Browse", "Semantic Search", "Processing", "Favorites", "Profile"]
if user.get("is_admin"):
    nav_pages += ["Stats", "Admin: Users"]

with st.sidebar:
    page = st.radio("Navigation", nav_pages)
    st.divider()
    st.caption(f"Logged in as **{user['username']}**" + (" (admin)" if user.get("is_admin") else ""))
    if st.button("Logout"):
        del st.session_state["user"]
        st.rerun()

_screen_width = streamlit_js_eval(js_expressions="window.innerWidth", key="screen_width")
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
    title, authors, doc_url, description, content, categories, published_at = d
    st.divider()

    # Favorite toggle
    fav = db.is_favorite(user["id"], doc_id)
    fav_label = "★ Remove from favorites" if fav else "☆ Add to favorites"
    if st.button(fav_label, key=f"fav_toggle_{doc_id}"):
        if fav:
            db.remove_favorite(user["id"], doc_id)
        else:
            db.add_favorite(user["id"], doc_id)
        st.rerun()

    st.subheader(title)
    meta = []
    if doc_url:
        meta.append(f"[Open]({doc_url})")
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

    # Note & tags (only show if favorited)
    if fav or db.is_favorite(user["id"], doc_id):
        st.write("**Tags:**")
        all_tags = db.get_tags()
        doc_tags = db.get_document_tags(user["id"], doc_id)
        tag_names = [t["name"] for t in all_tags]

        col_t1, col_t2 = st.columns([3, 1])
        new_tag = col_t1.text_input("Add tag", key=f"addtag_input_{doc_id}")
        if col_t2.button("Add", key=f"addtag_btn_{doc_id}") and new_tag:
            tag_id = db.create_tag(new_tag.strip().lower())
            db.tag_document(user["id"], doc_id, tag_id)
            st.rerun()

        if doc_tags:
            st.write("Tags: " + ", ".join(f"`{t}`" for t in doc_tags))
            rm_tag = st.selectbox("Remove tag", [""] + doc_tags, key=f"rmtag_{doc_id}")
            if st.button("Remove", key=f"rmtagbtn_{doc_id}") and rm_tag:
                tag_obj = next((t for t in all_tags if t["name"] == rm_tag), None)
                if tag_obj:
                    db.untag_document(user["id"], doc_id, tag_obj["id"])
                    st.rerun()

        note_val = ""
        favs = db.get_user_favorites(user["id"])
        for f in favs:
            if f["id"] == doc_id:
                note_val = f["note"] or ""
                break
        note = st.text_area("Note", value=note_val, key=f"note_{doc_id}")
        if st.button("Save note", key=f"savenote_{doc_id}"):
            db.update_favorite_note(user["id"], doc_id, note)
            st.success("Note saved.")


# ─── Browse ─────────────────────────────────────────────────────────────────

if page == "Browse":
    st.title("Browse")

    c1, c2, c3 = st.columns(3)
    source = c1.selectbox("Source", ["all", "rss", "arxiv", "github"])
    days = c2.number_input("Collected last N days", min_value=1, max_value=365, value=30)
    search = c3.text_input("Search title")

    rows = db.fetch_documents_for_user(
        user_id=user["id"],
        since=datetime.now(timezone.utc) - timedelta(days=int(days)),
        source=source if source != "all" else None,
        search=search or None,
    )

    df = pd.DataFrame(rows, columns=["id", "source", "title", "published_at", "url"])
    st.caption(f"{len(df)} documents")

    sel = st.dataframe(
        df[["source", "title", "published_at"]],
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

    # Load user's saved defaults
    pref_novelty = float(user.get("pref_novelty_threshold") or 0.6)
    pref_digest_days = int(user.get("pref_digest_days") or 7)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.subheader("Deduplicate")
        st.write("Find near-duplicate documents using cosine similarity.")
        if user.get("is_admin"):
            if st.button("Run dedup"):
                with st.spinner("Finding duplicates..."):
                    from processors.dedup import main as dedup_main
                    st.session_state["proc_output"] = capture_run(dedup_main)
        else:
            st.info("Admin only.")

    with col2:
        st.subheader("Novelty")
        st.write("Score documents by how different they are from the rest.")
        novelty_threshold = st.slider("Threshold", 0.0, 1.0, pref_novelty, 0.05, key="novelty_threshold")
        novelty_time_field = st.selectbox("Filter by", ["published_since", "collected_since", "updated_since"], key="novelty_time_field")
        novelty_days = st.number_input("Last N days", min_value=1, max_value=365, value=7, key="novelty_days")
        if st.button("Run novelty"):
            with st.spinner("Computing novelty scores..."):
                from processors.novelty import main as novelty_main
                import processors.novelty as _novelty_mod
                _novelty_mod.NOVELTY_THRESHOLD = novelty_threshold
                kwargs = {novelty_time_field: int(novelty_days), "user_id": user["id"]}
                st.session_state["proc_output"] = capture_run(lambda: novelty_main(**kwargs))

    with col3:
        st.subheader("Cluster")
        st.write("Group documents into topic clusters using HDBSCAN.")
        new_only = st.checkbox("Show only new articles")
        if st.button("Run cluster"):
            with st.spinner("Clustering..."):
                from processors.cluster import main as cluster_main
                st.session_state["proc_output"] = capture_run(lambda: cluster_main(new=new_only, user_id=user["id"]))

    with col4:
        st.subheader("Digest")
        st.write("Generate a meta-summary of recent article summaries.")
        digest_days = st.number_input("Published last N days", min_value=1, max_value=15, value=pref_digest_days, key="digest_days")
        digest_novelty = st.checkbox("Novel articles only", key="digest_novelty")
        digest_threshold = None
        if digest_novelty:
            digest_threshold = st.slider("Novelty threshold", 0.0, 1.0, 0.5, 0.05, key="digest_threshold")
        if st.button("Run digest"):
            with st.spinner("Generating digest..."):
                from processors.summarize import digest as digest_main
                st.session_state["proc_output"] = capture_run(
                    lambda: digest_main(
                        published_since=int(digest_days),
                        novelty_threshold=digest_threshold,
                        model=ollama_model,
                        user_id=user["id"],
                    )
                )

    if "proc_output" in st.session_state:
        st.divider()
        clean = re.sub(r"\033\[[0-9;]*m", "", st.session_state["proc_output"] or "Done.")
        wrapped = "\n".join(
            textwrap.fill(line, width=wrap_width, subsequent_indent="", break_long_words=True)
            if len(line) > wrap_width else line
            for line in clean.splitlines()
        )
        st.code(wrapped)


# ─── Favorites ────────────────────────────────────────────────────────────────

elif page == "Favorites":
    from ui.favorites import show as show_favorites
    show_favorites(user)


# ─── Profile ──────────────────────────────────────────────────────────────────

elif page == "Profile":
    from ui.profile import show as show_profile
    show_profile(user)


# ─── Admin: Users ─────────────────────────────────────────────────────────────

elif page == "Admin: Users":
    if not user.get("is_admin"):
        st.error("Admin access required.")
        st.stop()
    from ui.admin_users import show as show_admin_users
    show_admin_users()
