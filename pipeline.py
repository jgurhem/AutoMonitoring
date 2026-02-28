import argparse
from processors.cluster import main as cluster_main
from processors.dedup import main as dedup_main
from processors.novelty import main as novelty_main
from processors.summarize import digest as digest_main

def main():
    parser = argparse.ArgumentParser(description="Run the processing pipeline")
    subparsers = parser.add_subparsers(dest="command")

    cluster_parser = subparsers.add_parser("cluster", help="Cluster documents")
    cluster_parser.add_argument("--new", action="store_true", help="Only show articles from the last few days")

    subparsers.add_parser("dedup", help="Find near-duplicate documents")

    novelty_parser = subparsers.add_parser("novelty", help="Score document novelty")
    novelty_parser.add_argument("--published-since", type=int, metavar="DAYS", help="Only score documents published in the last N days")
    novelty_parser.add_argument("--collected-since", type=int, metavar="DAYS", help="Only score documents collected in the last N days")
    novelty_parser.add_argument("--updated-since", type=int, metavar="DAYS", help="Only score documents updated in the last N days")

    digest_parser = subparsers.add_parser("digest", help="Generate a meta-summary digest of recent articles")
    digest_parser.add_argument("--published-since", type=int, metavar="DAYS", default=7, help="Articles published in the last N days (default: 7)")
    digest_parser.add_argument("--novelty-threshold", type=float, metavar="FLOAT", help="Only include articles with novelty score above this threshold (e.g. 0.5)")
    digest_parser.add_argument("--model", type=str, default="mixtral", help="Ollama model to use (default: mixtral)")
    digest_parser.add_argument("--num-predict", type=int, default=4096, help="Max tokens to generate (default: 4096)")

    args = parser.parse_args()

    if args.command is None:
        cluster_main()
        dedup_main()
        novelty_main()
    elif args.command == "cluster":
        cluster_main(new=args.new)
    elif args.command == "dedup":
        dedup_main()
    elif args.command == "novelty":
        novelty_main(
            published_since=args.published_since,
            collected_since=args.collected_since,
            updated_since=args.updated_since,
        )
    elif args.command == "digest":
        digest_main(
            published_since=args.published_since,
            novelty_threshold=args.novelty_threshold,
            model=args.model,
            num_predict=args.num_predict,
        )

if __name__ == "__main__":
    main()
