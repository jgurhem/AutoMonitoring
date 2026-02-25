import logging
from db import fetch_novelty_scores

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

NOVELTY_THRESHOLD = 0.5

def main():
    docs = fetch_novelty_scores()
    scored = [
        {**d, "novelty_score": 1 - d["nearest_similarity"]}
        for d in docs
        if d["nearest_similarity"] is not None
    ]
    novel = [d for d in scored if d["novelty_score"] > NOVELTY_THRESHOLD]
    novel.sort(key=lambda d: d["novelty_score"], reverse=True)

    for d in novel:
        logger.info(f"[{d['novelty_score']:.4f}] {d['id']} \"{d['title']}\"")

    logger.info(
        f"Summary: {len(novel)} novel / {len(scored)} total "
        f"(threshold={NOVELTY_THRESHOLD})"
    )

