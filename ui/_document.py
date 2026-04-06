import streamlit as st

import core.db as db


def show_document(user, doc_id):
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
