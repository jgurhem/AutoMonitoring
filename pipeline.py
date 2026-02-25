import argparse
from processors.cluster import main as cluster_main
from processors.dedup import main as dedup_main
from processors.novelty import main as novelty_main

def main():
    parser = argparse.ArgumentParser(description="Run the processing pipeline")
    subparsers = parser.add_subparsers(dest="command")

    cluster_parser = subparsers.add_parser("cluster", help="Cluster documents")
    cluster_parser.add_argument("--new", action="store_true", help="Only show articles from the last few days")

    subparsers.add_parser("dedup", help="Find near-duplicate documents")
    subparsers.add_parser("novelty", help="Score document novelty")

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
        novelty_main()

if __name__ == "__main__":
    main()
