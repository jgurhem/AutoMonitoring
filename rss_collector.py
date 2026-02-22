import feedparser
from newspaper import Article
from datetime import datetime
import hashlib
from db import insert_document

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
                article = Article(entry.link)
                article.download()
                article.parse()

                description = article.text.strip()
                if not description:
                    continue

                authors = article.authors or (
                    [entry.author] if entry.get("author") else []
                )

                articles.append({
                    "id": hash_text(description),
                    "source": "rss",
                    "title": entry.title,
                    "authors": authors,
                    "url": entry.link,
                    "published": entry.get("published", ""),
                    "description": description,
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