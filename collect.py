import argparse
from arxiv_collector import collect_arxiv
from rss_collector import collect_rss
from embed import run as embed_run
from summarize import run as summarize_run
from logger import get_logger

logger = get_logger("collect")

def run_all():
    count = collect_arxiv()
    logger.info("%d papiers arxiv insérés en base", count)
    count = collect_rss()
    logger.info("%d articles rss insérés en base", count)
    embed_run()
    summarize_run()

def main():
    parser = argparse.ArgumentParser(description="Collect and process documents")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("arxiv", help="Collect from arXiv")
    subparsers.add_parser("rss", help="Collect from RSS feeds")
    subparsers.add_parser("embed", help="Compute embeddings")
    subparsers.add_parser("summarize", help="Summarize documents")

    args = parser.parse_args()

    if args.command is None:
        run_all()
    elif args.command == "arxiv":
        count = collect_arxiv()
        logger.info("%d papiers insérés en base", count)
    elif args.command == "rss":
        count = collect_rss()
        logger.info("%d articles insérés en base", count)
    elif args.command == "embed":
        embed_run()
    elif args.command == "summarize":
        summarize_run()

if __name__ == "__main__":
    main()
