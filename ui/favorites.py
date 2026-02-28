import csv
import io

import streamlit as st

import core.db as db


def _sort_ts(f, field):
    v = f.get(field)
    if v is None:
        return 0
    try:
        return v.timestamp()
    except Exception:
        return 0


def show(user: dict):
    st.title("Favorites")
    user_id = user["id"]

    favorites = db.get_user_favorites(user_id)
    all_tags = db.get_tags()
    all_doc_tags = db.get_all_document_tags_for_user(user_id)

    if not favorites:
        st.info("No favorites yet. Star documents from the Browse page.")
        return

    # ─── Search / sort / filter ───────────────────────────────────────────────
    col_s, col_so, col_f = st.columns([3, 2, 2])
    search_text = col_s.text_input("Search", placeholder="title or note…")
    sort_by = col_so.selectbox("Sort by", [
        "Favorited (newest)", "Favorited (oldest)",
        "Published (newest)", "Published (oldest)",
    ])
    filter_tag = col_f.selectbox("Filter by tag", ["(all)"] + [t["name"] for t in all_tags])

    # Apply filters
    if search_text:
        sl = search_text.lower()
        favorites = [
            f for f in favorites
            if sl in (f["title"] or "").lower() or sl in (f["note"] or "").lower()
        ]
    if filter_tag != "(all)":
        favorites = [f for f in favorites if filter_tag in all_doc_tags.get(f["id"], [])]

    # Apply sort
    reverse = "newest" in sort_by
    field = "favorited_at" if "Favorited" in sort_by else "published_at"
    favorites = sorted(favorites, key=lambda f: _sort_ts(f, field), reverse=reverse)

    if not favorites:
        st.info("No favorites match the current filters.")
        return

    # ─── Export ───────────────────────────────────────────────────────────────
    with st.expander("Export"):
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(["Title", "URL", "Published", "Source", "Note", "Tags"])
        for fav in favorites:
            tags = all_doc_tags.get(fav["id"], [])
            writer.writerow([
                fav["title"], fav["url"],
                str(fav["published_at"])[:10] if fav["published_at"] else "",
                fav.get("source", ""),
                fav["note"] or "",
                ", ".join(tags),
            ])
        st.download_button(
            "Download CSV", csv_buf.getvalue(), "favorites.csv", "text/csv",
            key="export_csv",
        )

        md_lines = ["# Favorites\n"]
        for fav in favorites:
            tags = all_doc_tags.get(fav["id"], [])
            md_lines.append(f"## {fav['title'] or fav['id']}")
            if fav["url"]:
                md_lines.append(f"**URL:** {fav['url']}")
            if fav["published_at"]:
                md_lines.append(f"**Published:** {str(fav['published_at'])[:10]}")
            if tags:
                md_lines.append(f"**Tags:** {', '.join(tags)}")
            if fav["note"]:
                md_lines.append(f"**Note:** {fav['note']}")
            md_lines.append("")
        st.download_button(
            "Download Markdown", "\n".join(md_lines), "favorites.md", "text/markdown",
            key="export_md",
        )

    st.divider()

    # ─── Batch operations ─────────────────────────────────────────────────────
    visible_ids = [f["id"] for f in favorites]
    selected_ids = [fid for fid in visible_ids if st.session_state.get(f"sel_{fid}", False)]

    sel_col1, sel_col2 = st.columns([1, 1])
    if sel_col1.button("Select all"):
        for fid in visible_ids:
            st.session_state[f"sel_{fid}"] = True
        st.rerun()
    if sel_col2.button("Deselect all"):
        for fid in visible_ids:
            st.session_state[f"sel_{fid}"] = False
        st.rerun()

    if selected_ids:
        st.write(f"**{len(selected_ids)} selected**")
        ba1, ba2, ba3 = st.columns([2, 4, 2])
        if ba1.button(f"Remove ({len(selected_ids)})"):
            for doc_id in selected_ids:
                db.remove_favorite(user_id, doc_id)
                st.session_state.pop(f"sel_{doc_id}", None)
            st.rerun()
        batch_tag = ba2.text_input(
            "batch_tag", key="batch_tag_input",
            label_visibility="collapsed", placeholder="Tag all selected…",
        )
        if ba3.button("Apply tag") and batch_tag:
            tag_id = db.create_tag(batch_tag.strip().lower())
            for doc_id in selected_ids:
                db.tag_document(user_id, doc_id, tag_id)
            st.rerun()

    st.divider()

    # ─── Favorites list ───────────────────────────────────────────────────────
    for fav in favorites:
        doc_tags = all_doc_tags.get(fav["id"], [])
        check_col, content_col = st.columns([1, 11])
        check_col.checkbox("Select", key=f"sel_{fav['id']}", label_visibility="collapsed")

        with content_col.expander(fav["title"] or fav["id"], expanded=False):
            col1, col2 = st.columns([6, 1])
            meta = []
            if fav["url"]:
                meta.append(f"[Open]({fav['url']})")
            if fav["published_at"]:
                meta.append(str(fav["published_at"])[:10])
            col1.write("  •  ".join(meta))

            if doc_tags:
                col1.write("Tags: " + ", ".join(f"`{t}`" for t in doc_tags))

            # Add tag
            new_tag = st.text_input("Add tag", key=f"newtag_{fav['id']}")
            if st.button("Add", key=f"addtag_{fav['id']}") and new_tag:
                tag_id = db.create_tag(new_tag.strip().lower())
                db.tag_document(user_id, fav["id"], tag_id)
                st.rerun()

            # Remove tag
            if doc_tags:
                remove_tag = st.selectbox("Remove tag", [""] + doc_tags, key=f"rmtag_{fav['id']}")
                if st.button("Remove tag", key=f"rmtagbtn_{fav['id']}") and remove_tag:
                    tag_obj = next((t for t in all_tags if t["name"] == remove_tag), None)
                    if tag_obj:
                        db.untag_document(user_id, fav["id"], tag_obj["id"])
                        st.rerun()

            # Note
            note = st.text_area("Note", value=fav["note"] or "", key=f"note_{fav['id']}")
            if st.button("Save note", key=f"savenote_{fav['id']}"):
                db.update_favorite_note(user_id, fav["id"], note)
                st.success("Note saved.")

            # Remove from favorites — with confirm
            confirm_key = f"confirm_unfav_{fav['id']}"
            if st.session_state.get(confirm_key):
                st.warning("Remove from favorites?")
                c1, c2 = st.columns(2)
                if c1.button("Yes, remove", key=f"unfav_yes_{fav['id']}"):
                    db.remove_favorite(user_id, fav["id"])
                    del st.session_state[confirm_key]
                    st.rerun()
                if c2.button("Cancel", key=f"unfav_no_{fav['id']}"):
                    del st.session_state[confirm_key]
                    st.rerun()
            else:
                if col2.button("★ Remove", key=f"unfav_{fav['id']}"):
                    st.session_state[confirm_key] = True
                    st.rerun()
