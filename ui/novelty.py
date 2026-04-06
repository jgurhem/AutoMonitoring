import re
import textwrap

import streamlit as st


def show(user, capture_run, wrap_width):
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
            st.session_state["proc_output"] = capture_run(lambda: novelty_main(**kwargs))

    if "proc_output" in st.session_state:
        st.divider()
        clean = re.sub(r"\033\[[0-9;]*m", "", st.session_state["proc_output"] or "Done.")
        wrapped = "\n".join(
            textwrap.fill(line, width=wrap_width, subsequent_indent="", break_long_words=True)
            if len(line) > wrap_width else line
            for line in clean.splitlines()
        )
        st.code(wrapped)
