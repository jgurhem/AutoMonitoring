from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from core.db import fetch_documents_without_summary, save_summary, fetch_summaries_since
from core.logger import get_logger

logger = get_logger("summarize")

MODEL = "mixtral"
BATCH_SIZE = 10
MAX_CHARS = 400000

SUMMARIZE_PROMPT = PromptTemplate.from_template(
    "Summarize the following article in 5 to 10 sentences. Identify key points and main contributions. Be concise and factual.\n\n"
    "Title: {title}\n\n{body}\n\nSummary:"
)

DIGEST_PROMPT = PromptTemplate.from_template(
    "You are given summaries of {count} recent articles. "
    "Write a concise digest highlighting main themes, trends, and notable findings.\n\n"
    "{entries}\n\nDigest:"
)


def build_body(doc: dict) -> str:
    parts = [doc.get("description") or "", doc.get("content") or ""]
    text = "\n\n".join(p.strip() for p in parts if p.strip())
    return text[:MAX_CHARS]


def run(model: str = MODEL, num_predict: int = 2048):
    llm = OllamaLLM(model=model, temperature=0.2, num_predict=num_predict)
    chain = SUMMARIZE_PROMPT | llm

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
            for attempt in range(1, 6):
                try:
                    summary = chain.invoke({"title": doc["title"] or "", "body": body})
                    save_summary(doc["id"], summary.strip())
                    logger.info("Summarized: %s", doc["title"])
                    total += 1
                    break
                except Exception as e:
                    logger.error("Failed %s (attempt %d/5): %s", doc["id"], attempt, e)
                    if attempt == 5:
                        logger.error("Giving up on %s after 5 attempts.", doc["id"])
                        raise e

    logger.info("Done. %d documents summarized.", total)


def digest(
    published_since: int = 7,
    novelty_threshold: float | None = None,
    model: str = MODEL,
    num_predict: int = 2048,
    user_id=None,
):
    docs = fetch_summaries_since(published_since, novelty_threshold, user_id=user_id)
    if not docs:
        return {"digest_text": None, "articles": []}

    logger.info("Generating digest from %d articles...", len(docs))

    entries = "\n".join(
        f"- {d['title']}: {(d['summary'] or '')[:MAX_CHARS]}"
        for d in docs
    )

    llm = OllamaLLM(model=model, temperature=0.3, num_predict=num_predict)
    chain = DIGEST_PROMPT | llm

    result = None
    for attempt in range(1, 6):
        try:
            result = chain.invoke({"count": len(docs), "entries": entries})
            logger.info("Digest complete")
            break
        except Exception as e:
            logger.error("Digest failed (attempt %d/5): %s", attempt, e)
            if attempt == 5:
                logger.error("Giving up on digest after 5 attempts.")
                raise e

    return {"digest_text": result.strip(), "articles": docs}
