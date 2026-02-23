import feedparser
import trafilatura
from datetime import datetime, timezone
import hashlib
from db import insert_document, is_recently_collected
from logger import get_logger

logger = get_logger("rss")

RSS_FEEDS = [
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://towardsdatascience.com/feed",
    "https://machinelearningmastery.com/blog/feed/",
    "https://www.marktechpost.com/feed/",
    "https://news.mit.edu/rss/topic/artificial-intelligence2",
    "https://www.aiiottalk.com/feed/",
    "https://research.google/blog/rss/",
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://tldr.tech/api/rss/ai",
    "https://tldr.tech/api/rss/tech",
    "https://tldr.tech/api/rss/dev",
    "https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml",
    "https://www.actuia.com/feed/",
    "https://www.aiplusinfo.com/feed/",
    "https://deepmind.com/blog/feed/basic/",
    "https://www.greatlearning.in/blog/category/artificial-intelligence/feed/",
]

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def collect_rss(max_per_feed=10):
    count = 0

    for feed_url in RSS_FEEDS:
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

                insert_document({
                    "id": hash_text(content),
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
                count += 1

            except Exception as e:
                logger.error("Erreur sur %s: %s", entry.link, e)

    return count

if __name__ == "__main__":
    count = collect_rss()
    logger.info("%d articles insérés en base", count)