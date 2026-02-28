import feedparser
import trafilatura
from datetime import datetime, timezone
import hashlib
from core.db import insert_document, is_recently_collected
from core.logger import get_logger

logger = get_logger("rss")


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def collect_rss_feeds(feeds: list[dict], max_per_feed: int = 10) -> dict[int, list[str]]:
    """Collect from a list of {feed_id, url} dicts. Returns {feed_id: [doc_ids]}."""
    results: dict[int, list[str]] = {}

    for feed_info in feeds:
        feed_id = feed_info["feed_id"]
        feed_url = feed_info["url"]
        doc_ids: list[str] = []

        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:max_per_feed]:
            try:
                if is_recently_collected(entry.link):
                    logger.debug("Ignoré (déjà collecté): %s", entry.link)
                    continue

                downloaded = trafilatura.fetch_url(entry.link)
                content = trafilatura.extract(downloaded, include_comments=False)
                if not content:
                    continue

                metadata = trafilatura.extract_metadata(downloaded)
                authors = metadata.author.split(", ") if metadata and metadata.author else (
                    [entry.author] if entry.get("author") else []
                )

                doc_id = hash_text(content)
                insert_document({
                    "id": doc_id,
                    "source": "rss",
                    "title": entry.title,
                    "authors": authors,
                    "url": entry.link,
                    "published": entry.get("published", ""),
                    "description": entry.get("summary", ""),
                    "content": content,
                    "collected_at": datetime.now(timezone.utc).isoformat()
                })
                logger.info("Inséré: %s", entry.title)
                doc_ids.append(doc_id)

            except Exception as e:
                logger.error("Erreur sur %s: %s", entry.link, e)

        results[feed_id] = doc_ids

    return results
