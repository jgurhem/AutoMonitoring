import streamlit as st


def _render_members(user, members, new_only):
    visible = [m for m in members if m["recent"]] if new_only else members
    visible = sorted(visible, key=lambda m: m["novelty"], reverse=True)
    for m in visible:
        col_new, col_score, col_title = st.columns([1, 1, 8])
        if m["recent"]:
            col_new.markdown("**[NEW]**")
        col_score.markdown(f"`{m['novelty']:.2f}`")
        if col_title.button(m["title"], key=f"cls_{m['id']}"):
            st.session_state["cluster_selected"] = m["id"]


def show(user):
    st.title("Cluster")
    st.write("Group documents into topic clusters using HDBSCAN.")

    new_only = st.checkbox("Show only new articles")

    if st.button("Run cluster"):
        with st.spinner("Clustering..."):
            from processors.cluster import main as cluster_main
            try:
                st.session_state["cluster_result"] = cluster_main(user_id=user["id"])
            except Exception as e:
                st.error(str(e))

    if "cluster_result" in st.session_state:
        result = st.session_state["cluster_result"]
        st.divider()
        st.caption(f"{result['n_clusters']} cluster(s), {result['n_noise']} noise document(s)")

        for cluster in result["clusters"]:
            with st.expander(f"{cluster['label']} ({cluster['member_count']} docs)"):
                if cluster["is_subclustered"]:
                    for sub in cluster["subclusters"]:
                        st.markdown(f"**{sub['label']}** ({sub['member_count']} docs)")
                        _render_members(user, sub["members"], new_only)
                else:
                    _render_members(user, cluster["members"], new_only)

        if result["noise"]:
            with st.expander(f"Noise ({result['n_noise']} docs)"):
                _render_members(user, result["noise"], new_only)

    if "cluster_selected" in st.session_state:
        st.divider()
        from ui._document import show_document
        show_document(user, st.session_state["cluster_selected"])
