import pandas as pd
import streamlit as st

import core.db as db
from ui._document import show_document


def show(user):
    st.title("Semantic Search")

    @st.cache_resource
    def load_embedder():
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    query = st.text_input("Query")
    top_k = st.slider("Results", 5, 50, 10)

    if query:
        with st.spinner("Searching..."):
            vec = load_embedder().embed_query(query)
            rows = db.search_similar(vec, top_k=top_k)

        df = pd.DataFrame(rows, columns=["id", "source", "title", "url", "published_at", "similarity"])
        df["similarity"] = df["similarity"].round(4)

        sel = st.dataframe(
            df[["similarity", "source", "title", "published_at"]],
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
        )

        if sel.selection.rows:
            show_document(user, df.iloc[sel.selection.rows[0]]["id"])
