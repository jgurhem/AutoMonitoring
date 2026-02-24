import logging
import numpy as np
from sklearn.cluster import HDBSCAN
from collections import defaultdict
from db import fetch_all_embeddings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PREVIEW_SIZE = 20
# Sub-cluster the largest cluster if it has at least this many members
SUBCLUSTER_MIN_SIZE = 30
SUB_MIN_CLUSTER_SIZE = 2

def compute_novelty_scores(matrix: np.ndarray) -> np.ndarray:
    # embeddings are normalized, so cosine similarity = dot product
    sims = matrix @ matrix.T
    np.fill_diagonal(sims, -np.inf)
    return 1 - sims.max(axis=1)

def log_cluster(label: str, members: list, indent: str = ""):
    members.sort(key=lambda m: m["novelty"], reverse=True)
    logger.info(f"{indent}{label} ({len(members)} docs):")
    for m in members[:PREVIEW_SIZE]:
        logger.info(f"{indent}  [{m['novelty']:.4f}] {m['title']}")
    if len(members) > PREVIEW_SIZE:
        logger.info(f"{indent}  ... and {len(members) - PREVIEW_SIZE} more")

def main():
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
        clusters[label].append({"title": doc["title"], "novelty": float(score), "embedding": vec})

    noise_docs = clusters.pop(-1, [])

    biggest_id = max(clusters, key=lambda k: len(clusters[k]), default=None)

    for cluster_id, members in sorted(clusters.items()):
        if cluster_id == biggest_id and len(members) >= SUBCLUSTER_MIN_SIZE:
            sub_matrix = np.stack([m["embedding"] for m in members])
            sub_labels = HDBSCAN(copy=False, min_cluster_size=SUB_MIN_CLUSTER_SIZE, metric="euclidean").fit_predict(sub_matrix)
            sub_novelty = compute_novelty_scores(sub_matrix)

            sub_clusters = defaultdict(list)
            for m, slabel, snovelty in zip(members, sub_labels, sub_novelty):
                sub_clusters[slabel].append({"title": m["title"], "novelty": float(snovelty)})

            sub_noise = sub_clusters.pop(-1, [])
            logger.info(f"Cluster {cluster_id} ({len(members)} docs) [sub-clustered]:")
            for sub_id, sub_members in sorted(sub_clusters.items()):
                log_cluster(f"  Sub-cluster {cluster_id}.{sub_id}", sub_members, indent="  ")
            if sub_noise:
                log_cluster(f"  Sub-cluster {cluster_id}.noise", sub_noise, indent="  ")
        else:
            log_cluster(f"Cluster {cluster_id}", members)

    if noise_docs:
        log_cluster("Noise", noise_docs)

    n_clusters = len(clusters)
    n_noise = len(noise_docs)
    logger.info(f"Summary: {n_clusters} cluster(s), {n_noise} noise document(s)")

if __name__ == "__main__":
    main()
