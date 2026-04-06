import logging
from core.db import fetch_novelty_scores

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEFAULT_NOVELTY_THRESHOLD = 0.5

def main(published_since=7, collected_since=None, updated_since=None, user_id=None, threshold=DEFAULT_NOVELTY_THRESHOLD):
    docs = fetch_novelty_scores(
        published_since=published_since,
        collected_since=collected_since,
        updated_since=updated_since,
        user_id=user_id,
    )
    scored = [
        {**d, "novelty_score": 1 - d["nearest_similarity"]}
        for d in docs
        if d["nearest_similarity"] is not None
    ]
    novel = [d for d in scored if d["novelty_score"] > threshold]
    novel.sort(key=lambda d: d["novelty_score"], reverse=True)

    logger.info(
        "Novelty: %d novel / %d total (threshold=%.2f)",
        len(novel), len(scored), threshold,
    )

    return {
        "docs": [{"id": d["id"], "title": d["title"], "novelty_score": d["novelty_score"]} for d in novel],
        "total_scored": len(scored),
        "threshold": threshold,
    }
