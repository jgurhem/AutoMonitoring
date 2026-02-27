#!/usr/bin/env python3
"""Summarize documents using Mixtral-8x7B running locally via Ollama.

Requires:
  - Ollama installed and running (https://ollama.com)
  - Model pulled: ollama pull mixtral
  - DB migration: ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT;
"""

from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from core.db import fetch_documents_without_summary, save_summary
from core.logger import get_logger

logger = get_logger("summarize")

MODEL = "mixtral"
BATCH_SIZE = 10
MAX_CONTENT_CHARS = 400000

PROMPT = PromptTemplate.from_template(
    "Summarize the following article in 5 to 10 sentences. Identify key points and main contributions. Be concise and factual.\n\n"
    "Title: {title}\n\n{body}\n\nSummary:"
)


def build_body(doc: dict) -> str:
    parts = [doc.get("description") or "", doc.get("content") or ""]
    text = "\n\n".join(p.strip() for p in parts if p.strip())
    return text[:MAX_CONTENT_CHARS]


def run(model: str = MODEL, num_predict: int = 2048):
    llm = OllamaLLM(model=model, temperature=0.2, num_predict=num_predict)
    chain = PROMPT | llm

    total = 0
    while True:
        docs = fetch_documents_without_summary(batch_size=BATCH_SIZE)
        if not docs:
            break

        for doc in docs:
            body = build_body(doc)
            if not body:
                logger.info("Skipping %s (no content)", doc["id"])
                continue
            try:
                summary = chain.invoke({"title": doc["title"] or "", "body": body})
                save_summary(doc["id"], summary.strip())
                logger.info("Summarized: %s", doc["title"])
                total += 1
            except Exception as e:
                logger.error("Failed %s: %s", doc["id"], e)
                if "status code: 500" in str(e):
                    logger.error("Model unavailable, aborting.")
                    return

    logger.info("Done. %d documents summarized.", total)
