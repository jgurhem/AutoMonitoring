import arxiv
import json
from datetime import datetime
import hashlib

SEARCH_QUERY = "artificial intelligence OR large language model OR transformer"

def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def collect_arxiv(max_results=20):
    results = []

    search = arxiv.Search(
        query=SEARCH_QUERY,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    for paper in search.results():
        content = paper.summary.strip()

        results.append({
            "id": hash_text(content),
            "source": "arxiv",
            "title": paper.title,
            "authors": [a.name for a in paper.authors],
            "published": paper.published.isoformat(),
            "url": paper.entry_id,
            "content": content,
            "categories": paper.categories,
            "collected_at": datetime.utcnow().isoformat()
        })

    return results

if __name__ == "__main__":
    data = collect_arxiv()
    with open("arxiv_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ arXiv collecté: {len(data)} papiers")