import arxiv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib
from db import insert_document, is_recently_collected
from logger import get_logger

logger = get_logger("arxiv")

DEFAULT_MAX_RESULTS = 10

SEARCHES = [
    {
        "query": "(artificial intelligence OR large language model OR transformer OR agent OR Deep Learning) AND (cat:cs.AI OR cat:cs.CL OR cat:cs.LG OR cat:cs.CV OR cat:cs.NE OR cat:cs.MA)",
        "sort_by": arxiv.SortCriterion.SubmittedDate,
        "max_results": 50,
    },
    {
        "query": "artificial intelligence OR large language model OR transformer",
        "sort_by": arxiv.SortCriterion.SubmittedDate,
        "max_results": 50,
    },
    {
        "query": "artificial intelligence OR large language model OR transformer",
        "sort_by": arxiv.SortCriterion.Relevance,
        "max_results": 50,
    },
    {
        "query": "au:'Yann LeCun' AND cat:cs.AI",
        "sort_by": arxiv.SortCriterion.SubmittedDate,
    },
    {
        "query": "au:'Torsten Hoefler'",
        "sort_by": arxiv.SortCriterion.SubmittedDate,
    },
    {
        "query": "au:'Jack Dongarra'",
        "sort_by": arxiv.SortCriterion.SubmittedDate,
    },
]

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def fetch_arxiv_content(html_url: str) -> str | None:
    response = requests.get(html_url, timeout=15)
    if not response.ok:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # Replace each <math> tag with its LaTeX alttext
    for math in soup.find_all("math"):
        latex = math.get("alttext", "")
        math.replace_with(f"${latex}$" if latex else "")

    # Extract the main article body
    article = soup.find("article") or soup.find("body")
    return article.get_text(separator="\n", strip=True) if article else None

def collect_arxiv():
    count = 0

    client = arxiv.Client()
    seen = set()

    for s in SEARCHES:
        search = arxiv.Search(
            query=s["query"],
            max_results=s.get("max_results", DEFAULT_MAX_RESULTS),
            sort_by=s["sort_by"],
        )
        for paper in client.results(search):
            if paper.entry_id in seen:
                continue
            seen.add(paper.entry_id)

            description = paper.summary.strip()

            if is_recently_collected(paper.entry_id):
                logger.debug("Ignoré (déjà collecté): %s", paper.entry_id)
                continue

            html_url = paper.entry_id.replace("/abs/", "/html/")
            content = fetch_arxiv_content(html_url)

            logger.info("Inséré: %s", paper.title)
            insert_document({
                "id": hash_text(description),
                "source": "arxiv",
                "title": paper.title,
                "authors": [a.name for a in paper.authors],
                "url": paper.entry_id,
                "description": description,
                "content": content,
                "categories": paper.categories,
                "published": paper.published.isoformat(),
                "updated_at": paper.updated.isoformat(),
                "collected_at": datetime.now(timezone.utc).isoformat(),
            })
            count += 1

    return count

if __name__ == "__main__":
    count = collect_arxiv()
    logger.info("%d papiers insérés en base", count)