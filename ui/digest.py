import re
import textwrap

import streamlit as st


def show(user, capture_run, wrap_width, ollama_model):
    st.title("Digest")
    st.write("Generate a meta-summary of recent article summaries.")

    pref_digest_days = int(user.get("pref_digest_days") or 7)

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
