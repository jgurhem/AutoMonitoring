from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from core.db import fetch_summaries_since
from core.logger import get_logger

logger = get_logger("digest")

MODEL = "mixtral"
MAX_SUMMARY_CHARS = 500

PROMPT = PromptTemplate.from_template(
    "You are given summaries of {count} recent articles. "
    "Write a concise digest highlighting main themes, trends, and notable findings.\n\n"
    "{entries}\n\nDigest:"
)


def main(
    published_since: int = 7,
    novelty_threshold: float | None = None,
    model: str = MODEL,
    num_predict: int = 4096,
    user_id=None,
):
    docs = fetch_summaries_since(published_since, novelty_threshold, user_id=user_id)
    if not docs:
        logger.info("No articles found for the given parameters.")
        return

    logger.info("Generating digest from %d articles...", len(docs))

    entries = "\n".join(
        f"- {d['title']}: {(d['summary'] or '')[:MAX_SUMMARY_CHARS]}"
        for d in docs
    )

    llm = OllamaLLM(model=model, temperature=0.3, num_predict=num_predict)
    chain = PROMPT | llm

    digest = chain.invoke({"count": len(docs), "entries": entries})
    logger.info("Digest:\n%s", digest.strip())
