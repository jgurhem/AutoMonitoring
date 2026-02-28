import streamlit as st
import core.db as db


def show():
    st.title("Admin: Dedup")

    threshold = st.slider("Similarity threshold", 0.90, 0.99, 0.95, 0.01)
    if st.button("Scan for duplicates"):
        with st.spinner("Scanning..."):
            st.session_state["dedup_pairs"] = db.fetch_near_duplicates(threshold=threshold)

    pairs = st.session_state.get("dedup_pairs")
    if pairs is None:
        return

    if not pairs:
        st.info("No duplicates found above this threshold.")
        return

    st.write(f"**{len(pairs)} duplicate pair(s) found.**")
    st.divider()

    for i, pair in enumerate(pairs):
        st.write(f"**Pair {i + 1}** — similarity: {pair['similarity']:.3f}")

        col1, col2, col3, col4 = st.columns([1, 4, 2, 1])
        col1.write(pair["source1"] or "")
        col2.write(pair["title1"] or "")
        col3.write(str(pair["published_at1"])[:10] if pair["published_at1"] else "")
        if col4.button("Delete A", key=f"del_a_{i}"):
            db.delete_document(pair["id1"])
            del st.session_state["dedup_pairs"]
            st.rerun()

        col1b, col2b, col3b, col4b = st.columns([1, 4, 2, 1])
        col1b.write(pair["source2"] or "")
        col2b.write(pair["title2"] or "")
        col3b.write(str(pair["published_at2"])[:10] if pair["published_at2"] else "")
        if col4b.button("Delete B", key=f"del_b_{i}"):
            db.delete_document(pair["id2"])
            del st.session_state["dedup_pairs"]
            st.rerun()

        st.divider()
