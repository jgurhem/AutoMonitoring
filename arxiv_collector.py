import arxiv
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import hashlib
from db import insert_document

SEARCH_QUERY = "artificial intelligence OR large language model OR transformer"

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
    results = []

    search = arxiv.Search(
        query=SEARCH_QUERY,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    for paper in search.results():
        description = paper.summary.strip()

        html_url = paper.entry_id.replace("/abs/", "/html/")
        content = fetch_arxiv_content(html_url)

        results.append({
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
            "collected_at": datetime.utcnow().isoformat(),
        })

    return results

if __name__ == "__main__":
    docs = collect_arxiv()
    for doc in docs:
        insert_document(doc)
    print(f"✅ arXiv insérés en base: {len(docs)} papiers")