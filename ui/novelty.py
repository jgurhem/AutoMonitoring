import streamlit as st


def show(user):
    st.title("Novelty")
    st.write("Score documents by how different they are from the rest.")

    pref_novelty = float(user.get("pref_novelty_threshold") or 0.6)

    novelty_threshold = st.slider("Threshold", 0.0, 1.0, pref_novelty, 0.05, key="novelty_threshold")
    novelty_time_field = st.selectbox("Filter by", ["published_since", "collected_since", "updated_since"], key="novelty_time_field")
    novelty_days = st.number_input("Last N days", min_value=1, max_value=365, value=7, key="novelty_days")

    if st.button("Run novelty"):
        with st.spinner("Computing novelty scores..."):
            from processors.novelty import main as novelty_main
            kwargs = {novelty_time_field: int(novelty_days), "user_id": user["id"], "threshold": novelty_threshold}
            try:
                st.session_state["novelty_result"] = novelty_main(**kwargs)
            except Exception as e:
                st.error(str(e))

    if "novelty_result" in st.session_state:
        result = st.session_state["novelty_result"]
        st.divider()
        st.caption(f"{len(result['docs'])} novel / {result['total_scored']} total (threshold={result['threshold']})")

        for doc in result["docs"]:
            col_score, col_title = st.columns([1, 8])
            col_score.markdown(f"`{doc['novelty_score']:.2f}`")
            if col_title.button(doc["title"], key=f"nov_{doc['id']}"):
                st.session_state["novelty_selected"] = doc["id"]

    if "novelty_selected" in st.session_state:
        st.divider()
        from ui._document import show_document
        show_document(user, st.session_state["novelty_selected"])
