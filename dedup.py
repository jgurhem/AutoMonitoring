import logging
from db import fetch_near_duplicates

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

THRESHOLD = 0.95

def main():
    pairs = fetch_near_duplicates(threshold=THRESHOLD)
    for p in pairs:
        logger.info(
            f"[{p['similarity']:.4f}] {p['id1']} \"{p['title1']}\" ↔ {p['id2']} \"{p['title2']}\""
        )
    logger.info(f"Summary: {len(pairs)} duplicate pair(s) found (threshold={THRESHOLD})")

