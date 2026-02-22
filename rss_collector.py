import feedparser
import trafilatura
from datetime import datetime
import hashlib
from db import insert_document, is_recently_collected

RSS_FEEDS = [
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://towardsdatascience.com/feed",
    "https://venturebeat.com/category/ai/feed/"
]

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def collect_rss():
    articles = []

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
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

                articles.append({
                    "id": hash_text(content),
                    "source": "rss",
                    "title": entry.title,
                    "authors": authors,
                    "url": entry.link,
                    "published": entry.get("published", ""),
                    "description": entry.get("summary", ""),
                    "content": content,
                    "collected_at": datetime.utcnow().isoformat()
                })

            except Exception as e:
                print(f"[RSS] Erreur: {e}")

    return articles

if __name__ == "__main__":
    docs = collect_rss()
    for doc in docs:
        insert_document(doc)
    print(f"✅ RSS insérés en base: {len(docs)} articles")