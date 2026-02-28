import argparse
from processors.embed import run as embed_run
from processors.summarize import run as summarize_run
from core.logger import get_logger
import core.db as db

logger = get_logger("collect")


def run_rss():
    from collectors.rss import collect_rss_feeds
    feeds = db.get_all_rss_feeds_with_subscribers()
    if not feeds:
        logger.info("No RSS feeds with subscribers found.")
        return
    result = collect_rss_feeds([{"feed_id": f["feed_id"], "url": f["url"]} for f in feeds])
    total = 0
    for feed in feeds:
        doc_ids = result.get(feed["feed_id"], [])
        for doc_id in doc_ids:
            for user_id in feed["subscriber_ids"]:
                db.link_document_to_user(user_id, doc_id)
        total += len(doc_ids)
    logger.info("%d articles RSS insérés en base", total)


def run_arxiv():
    from collectors.arxiv import collect_arxiv_searches
    searches = db.get_all_arxiv_searches_with_subscribers()
    if not searches:
        logger.info("No arXiv searches with subscribers found.")
        return
    result = collect_arxiv_searches([
        {"search_id": s["search_id"], "query": s["query"], "max_results": s["max_results"]}
        for s in searches
    ])
    total = 0
    for search in searches:
        doc_ids = result.get(search["search_id"], [])
        for doc_id in doc_ids:
            for user_id in search["subscriber_ids"]:
                db.link_document_to_user(user_id, doc_id)
        total += len(doc_ids)
    logger.info("%d papiers arXiv insérés en base", total)


def run_all(model, num_predict):
    run_arxiv()
    run_rss()
    embed_run()
    summarize_run(model=model, num_predict=num_predict)


def main():
    parser = argparse.ArgumentParser(description="Collect and process documents")
    parser.add_argument("--model", default="mixtral", help="Ollama model to use (default: mixtral)")
    parser.add_argument("--num-predict", type=int, default=2048, help="Max tokens to generate (default: 2048)")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("arxiv", help="Collect from arXiv")
    subparsers.add_parser("rss", help="Collect from RSS feeds")
    subparsers.add_parser("embed", help="Compute embeddings")
    subparsers.add_parser("summarize", help="Summarize documents")

    args = parser.parse_args()

    if args.command is None:
        run_all(model=args.model, num_predict=args.num_predict)
    elif args.command == "arxiv":
        run_arxiv()
    elif args.command == "rss":
        run_rss()
    elif args.command == "embed":
        embed_run()
    elif args.command == "summarize":
        summarize_run(model=args.model, num_predict=args.num_predict)


if __name__ == "__main__":
    main()
