import argparse
from collectors.arxiv import collect_arxiv
from collectors.rss import collect_rss
from processors.embed import run as embed_run
from processors.summarize import run as summarize_run
from core.logger import get_logger

logger = get_logger("collect")

def run_all(model, num_predict):
    count = collect_arxiv()
    logger.info("%d papiers arxiv insérés en base", count)
    count = collect_rss()
    logger.info("%d articles rss insérés en base", count)
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
        count = collect_arxiv()
        logger.info("%d papiers insérés en base", count)
    elif args.command == "rss":
        count = collect_rss()
        logger.info("%d articles insérés en base", count)
    elif args.command == "embed":
        embed_run()
    elif args.command == "summarize":
        summarize_run(model=args.model, num_predict=args.num_predict)

if __name__ == "__main__":
    main()
