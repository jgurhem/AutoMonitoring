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
    _auth_tab = st.session_state.get("auth_tab", "Login")
    col_l, col_r, _ = st.columns([1, 1, 4])
    if col_l.button("Login", type="primary" if _auth_tab == "Login" else "secondary"):
        st.session_state["auth_tab"] = "Login"
        st.rerun()
    if col_r.button("Register", type="primary" if _auth_tab == "Register" else "secondary"):
        st.session_state["auth_tab"] = "Register"
        st.rerun()
    if _auth_tab == "Register":
        from ui.register import show as show_register
        show_register()
    else:
        from ui.login import show as show_login
        show_login()
    st.stop()

user = current_user()

# ─── Sidebar / navigation ─────────────────────────────────────────────────────

_arg_parser = argparse.ArgumentParser(add_help=False)
_arg_parser.add_argument("--model", default="mixtral")
_args, _ = _arg_parser.parse_known_args()
ollama_model = _args.model

PAGE_SIZE = 50

nav_pages = ["Browse", "Semantic Search", "Novelty", "Cluster", "Digest", "Favorites", "Profile"]
if user.get("is_admin"):
    nav_pages += ["Stats", "Admin: Users", "Admin: Dedup"]

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
    db.mark_document_read(user["id"], doc_id)
    d = db.fetch_document(doc_id)
    if not d:
        return
    title, authors, doc_url, description, content, categories, published_at = d
    st.divider()

    btn_col1, btn_col2 = st.columns([2, 1])

    # Favorite toggle
    fav = db.is_favorite(user["id"], doc_id)
    fav_label = "★ Remove from favorites" if fav else "☆ Add to favorites"
    if btn_col1.button(fav_label, key=f"fav_toggle_{doc_id}"):
        if fav:
            db.remove_favorite(user["id"], doc_id)
        else:
            db.add_favorite(user["id"], doc_id)
        st.rerun()

    if btn_col2.button("Mark as unread", key=f"unread_{doc_id}"):
        db.mark_document_unread(user["id"], doc_id)
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


# ─── Novelty ──────────────────────────────────────────────────────────────────

elif page == "Novelty":
    from ui.novelty import show as show_novelty
    show_novelty(user, capture_run, wrap_width)


# ─── Cluster ──────────────────────────────────────────────────────────────────

elif page == "Cluster":
    from ui.cluster import show as show_cluster
    show_cluster(user, capture_run, wrap_width)


# ─── Digest ───────────────────────────────────────────────────────────────────

elif page == "Digest":
    from ui.digest import show as show_digest
    show_digest(user, capture_run, wrap_width, ollama_model)


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


# ─── Admin: Dedup ─────────────────────────────────────────────────────────────

elif page == "Admin: Dedup":
    if not user.get("is_admin"):
        st.error("Admin access required.")
        st.stop()
    from ui.admin_dedup import show as show_admin_dedup
    show_admin_dedup()
