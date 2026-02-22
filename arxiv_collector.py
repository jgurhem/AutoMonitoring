import arxiv
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import hashlib
from db import insert_document, is_recently_collected

SEARCHES = [
    {
        "query": "artificial intelligence OR large language model OR transformer",
        "sort_by": arxiv.SortCriterion.SubmittedDate,
    },
    {
        "query": "artificial intelligence OR large language model OR transformer",
        "sort_by": arxiv.SortCriterion.Relevance,
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

def collect_arxiv(max_results=20):
    count = 0

    client = arxiv.Client()
    seen = set()

    for s in SEARCHES:
        search = arxiv.Search(
            query=s["query"],
            max_results=max_results,
            sort_by=s["sort_by"],
        )
        for paper in client.results(search):
            if paper.entry_id in seen:
                continue
            seen.add(paper.entry_id)

            description = paper.summary.strip()

            if is_recently_collected(paper.entry_id):
                print(f"[arXiv] Ignoré (déjà collecté): {paper.entry_id}")
                continue

            html_url = paper.entry_id.replace("/abs/", "/html/")
            content = fetch_arxiv_content(html_url)

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
    print(f"✅ arXiv insérés en base: {count} papiers")