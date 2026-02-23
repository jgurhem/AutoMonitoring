#!/usr/bin/env python3
"""Compute and store embeddings for documents that don't have one yet."""

from langchain_huggingface import HuggingFaceEmbeddings
from db import fetch_documents_without_embeddings, save_embedding
from logger import get_logger

logger = get_logger("embed")

BATCH_SIZE = 100
MODEL_NAME = "all-MiniLM-L6-v2"


def build_text(doc: dict) -> str:
    parts = [doc.get("title") or "", doc.get("description") or "", doc.get("content") or ""]
    return " ".join(p.strip() for p in parts if p.strip())


def main():
    embedder = HuggingFaceEmbeddings(model_name=MODEL_NAME)
    total = 0

    while True:
        docs = fetch_documents_without_embeddings(batch_size=BATCH_SIZE)
        if not docs:
            break

        texts = [build_text(d) for d in docs]
        embeddings = embedder.embed_documents(texts)

        for doc, emb in zip(docs, embeddings):
            save_embedding(doc["id"], emb)

        total += len(docs)
        logger.info("Embedded %d documents (total: %d)", len(docs), total)

    logger.info("Done. %d documents embedded.", total)


if __name__ == "__main__":
    main()
