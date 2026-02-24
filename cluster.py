import argparse
import logging
import os
import numpy as np
from datetime import datetime, timezone, timedelta
from sklearn.cluster import HDBSCAN
from collections import defaultdict
from db import fetch_all_embeddings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PREVIEW_SIZE = 20
# Sub-cluster the largest cluster if it has at least this many members
SUBCLUSTER_MIN_SIZE = 30
SUB_MIN_CLUSTER_SIZE = 2
RECENT_DAYS = 4
USE_COLORS = os.getenv("NO_COLOR") is None

def compute_novelty_scores(matrix: np.ndarray) -> np.ndarray:
    # embeddings are normalized, so cosine similarity = dot product
    sims = matrix @ matrix.T
    np.fill_diagonal(sims, -np.inf)
    return 1 - sims.max(axis=1)

def is_recent(published_at) -> bool:
    if published_at is None:
        return False
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - published_at < timedelta(days=RECENT_DAYS)

def log_cluster(label: str, members: list, indent: str = "", only_new: bool = False):
    visible = [m for m in members if m["recent"]] if only_new else members
    visible.sort(key=lambda m: m["novelty"], reverse=True)
    if not visible:
        return
    logger.info(f"{indent}{label} ({len(members)} docs):")
    for m in visible[:PREVIEW_SIZE]:
        marker = "[NEW] " if m["recent"] else "      "
        line = f"{indent}  {marker}[{m['novelty']:.4f}] {m['title']}"
        if m["recent"]:
            line = f"\033[32m{line}\033[0m" if USE_COLORS else line
        logger.info(line)
    if len(visible) > PREVIEW_SIZE:
        logger.info(f"{indent}  ... and {len(visible) - PREVIEW_SIZE} more")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--new", action="store_true", help="Only show articles published in the last RECENT_DAYS days")
    args = parser.parse_args()

    docs = fetch_all_embeddings()
    if not docs:
        logger.info("No documents with embeddings found.")
        return

    matrix = np.stack([d["embedding"] for d in docs])
    clusterer = HDBSCAN(copy=False, min_cluster_size=3, metric="euclidean")
    labels = clusterer.fit_predict(matrix)
    novelty_scores = compute_novelty_scores(matrix)

    clusters = defaultdict(list)
    for doc, label, score, vec in zip(docs, labels, novelty_scores, matrix):
        clusters[label].append({"title": doc["title"], "novelty": float(score), "embedding": vec, "recent": is_recent(doc["published_at"])})

    noise_docs = clusters.pop(-1, [])

    biggest_id = max(clusters, key=lambda k: len(clusters[k]), default=None)

    for cluster_id, members in sorted(clusters.items()):
        if cluster_id == biggest_id and len(members) >= SUBCLUSTER_MIN_SIZE:
            sub_matrix = np.stack([m["embedding"] for m in members])
            sub_labels = HDBSCAN(copy=False, min_cluster_size=SUB_MIN_CLUSTER_SIZE, metric="euclidean").fit_predict(sub_matrix)
            sub_novelty = compute_novelty_scores(sub_matrix)

            sub_clusters = defaultdict(list)
            for m, slabel, snovelty in zip(members, sub_labels, sub_novelty):
                sub_clusters[slabel].append({"title": m["title"], "novelty": float(snovelty), "recent": m["recent"]})

            sub_noise = sub_clusters.pop(-1, [])
            logger.info(f"Cluster {cluster_id} ({len(members)} docs) [sub-clustered]:")
            for sub_id, sub_members in sorted(sub_clusters.items()):
                log_cluster(f"  Sub-cluster {cluster_id}.{sub_id}", sub_members, indent="  ", only_new=args.new)
            if sub_noise:
                log_cluster(f"  Sub-cluster {cluster_id}.noise", sub_noise, indent="  ", only_new=args.new)
        else:
            log_cluster(f"Cluster {cluster_id}", members, only_new=args.new)

    if noise_docs:
        log_cluster("Noise", noise_docs, only_new=args.new)

    n_clusters = len(clusters)
    n_noise = len(noise_docs)
    logger.info(f"Summary: {n_clusters} cluster(s), {n_noise} noise document(s)")

if __name__ == "__main__":
    main()
