import streamlit as st
import core.db as db


def show(user: dict):
    st.title("Favorites")
    user_id = user["id"]

    favorites = db.get_user_favorites(user_id)
    all_tags = db.get_tags()
    tag_names = [t["name"] for t in all_tags]

    # Filter by tag
    filter_tag = st.selectbox("Filter by tag", ["(all)"] + tag_names)

    if not favorites:
        st.info("No favorites yet. Star documents from the Browse page.")
        return

    if filter_tag != "(all)":
        # Only show docs that have this tag
        filtered = []
        for fav in favorites:
            doc_tags = db.get_document_tags(user_id, fav["id"])
            if filter_tag in doc_tags:
                filtered.append(fav)
        favorites = filtered

    if not favorites:
        st.info(f"No favorites tagged with '{filter_tag}'.")
        return

    for fav in favorites:
        with st.expander(fav["title"] or fav["id"], expanded=False):
            col1, col2 = st.columns([6, 1])
            meta = []
            if fav["url"]:
                meta.append(f"[Open]({fav['url']})")
            if fav["published_at"]:
                meta.append(str(fav["published_at"])[:10])
            col1.write("  •  ".join(meta))

            # Tags
            doc_tags = db.get_document_tags(user_id, fav["id"])
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

            # Remove from favorites
            if col2.button("★ Remove", key=f"unfav_{fav['id']}"):
                db.remove_favorite(user_id, fav["id"])
                st.rerun()
