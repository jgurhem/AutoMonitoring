import re
import textwrap

import streamlit as st


def show(user, capture_run, wrap_width):
    st.title("Cluster")
    st.write("Group documents into topic clusters using HDBSCAN.")

    new_only = st.checkbox("Show only new articles")

    if st.button("Run cluster"):
        with st.spinner("Clustering..."):
            from processors.cluster import main as cluster_main
            st.session_state["proc_output"] = capture_run(lambda: cluster_main(new=new_only, user_id=user["id"]))

    if "proc_output" in st.session_state:
        st.divider()
        clean = re.sub(r"\033\[[0-9;]*m", "", st.session_state["proc_output"] or "Done.")
        wrapped = "\n".join(
            textwrap.fill(line, width=wrap_width, subsequent_indent="", break_long_words=True)
            if len(line) > wrap_width else line
            for line in clean.splitlines()
        )
        st.code(wrapped)
