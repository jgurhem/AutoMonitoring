import streamlit as st


def show(user, ollama_model):
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
            from processors.summarize import digest as digest_fn
            try:
                result = digest_fn(
                    published_since=int(digest_days),
                    novelty_threshold=digest_threshold,
                    model=ollama_model,
                    user_id=user["id"],
                )
                st.session_state["digest_result"] = result
            except Exception as e:
                st.error(str(e))

    if "digest_result" in st.session_state:
        result = st.session_state["digest_result"]
        st.divider()
        if result["digest_text"] is None:
            st.info("No articles found for the given parameters.")
        else:
            st.markdown(result["digest_text"])
            st.subheader(f"Sources ({len(result['articles'])} articles)")
            for article in result["articles"]:
                with st.expander(article.get("title") or "(no title)"):
                    if article.get("novelty_score") is not None:
                        st.caption(f"Novelty: {article['novelty_score']:.2f}")
                    summary = article.get("summary") or ""
                    st.write(summary[:400] + ("..." if len(summary) > 400 else ""))
