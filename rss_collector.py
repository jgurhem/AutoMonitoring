import feedparser
import trafilatura
from datetime import datetime, timezone
import hashlib
from db import insert_document, is_recently_collected

RSS_FEEDS = [
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://towardsdatascience.com/feed",
    "https://machinelearningmastery.com/blog/feed/",
    "https://www.marktechpost.com/feed/",
    "https://news.mit.edu/rss/topic/artificial-intelligence2",
    "https://ai2people.com/feed/",
    "https://www.aiiottalk.com/feed/",
    "https://research.google/blog/rss/",
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
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
                    print(f"[RSS] Ignoré (déjà collecté): {entry.link}")
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
                count += 1

            except Exception as e:
                print(f"[RSS] Erreur: {e}")

    return count

if __name__ == "__main__":
    count = collect_rss()
    print(f"✅ RSS insérés en base: {count} articles")