import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from sklearn.cluster import HDBSCAN
from collections import defaultdict
from core.db import fetch_all_embeddings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Sub-cluster the largest cluster if it has at least this many members
SUBCLUSTER_MIN_SIZE = 30
SUB_MIN_CLUSTER_SIZE = 2
RECENT_DAYS = 4

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

def main(new: bool = False, user_id=None):
    docs = fetch_all_embeddings(user_id=user_id)
    if not docs:
        logger.info("No documents with embeddings found.")
        return {"clusters": [], "noise": [], "n_clusters": 0, "n_noise": 0}

    matrix = np.stack([d["embedding"] for d in docs])
    clusterer = HDBSCAN(copy=False, min_cluster_size=3, metric="euclidean")
    labels = clusterer.fit_predict(matrix)
    novelty_scores = compute_novelty_scores(matrix)

    clusters = defaultdict(list)
    for doc, label, score, vec in zip(docs, labels, novelty_scores, matrix):
        clusters[label].append({
            "id": doc["id"],
            "title": doc["title"],
            "novelty": float(score),
            "embedding": vec,
            "recent": is_recent(doc["published_at"]),
        })

    noise_docs = clusters.pop(-1, [])
    noise = [{"id": m["id"], "title": m["title"], "novelty": m["novelty"], "recent": m["recent"]} for m in noise_docs]

    biggest_id = max(clusters, key=lambda k: len(clusters[k]), default=None)

    result_clusters = []
    for cluster_id, members in sorted(clusters.items()):
        if cluster_id == biggest_id and len(members) >= SUBCLUSTER_MIN_SIZE:
            sub_matrix = np.stack([m["embedding"] for m in members])
            sub_labels = HDBSCAN(copy=False, min_cluster_size=SUB_MIN_CLUSTER_SIZE, metric="euclidean").fit_predict(sub_matrix)
            sub_novelty = compute_novelty_scores(sub_matrix)

            sub_clusters = defaultdict(list)
            for m, slabel, snovelty in zip(members, sub_labels, sub_novelty):
                sub_clusters[slabel].append({
                    "id": m["id"],
                    "title": m["title"],
                    "novelty": float(snovelty),
                    "recent": m["recent"],
                })

            sub_noise = sub_clusters.pop(-1, [])
            subclusters = [
                {
                    "label": f"Sub-cluster {cluster_id}.{sub_id}",
                    "member_count": len(sub_members),
                    "members": sub_members,
                }
                for sub_id, sub_members in sorted(sub_clusters.items())
            ]
            if sub_noise:
                subclusters.append({
                    "label": f"Sub-cluster {cluster_id}.noise",
                    "member_count": len(sub_noise),
                    "members": sub_noise,
                })

            result_clusters.append({
                "label": f"Cluster {cluster_id} [sub-clustered]",
                "is_subclustered": True,
                "member_count": len(members),
                "members": None,
                "subclusters": subclusters,
            })
        else:
            result_clusters.append({
                "label": f"Cluster {cluster_id}",
                "is_subclustered": False,
                "member_count": len(members),
                "members": [{"id": m["id"], "title": m["title"], "novelty": m["novelty"], "recent": m["recent"]} for m in members],
                "subclusters": None,
            })

    n_clusters = len(clusters)
    n_noise = len(noise_docs)
    logger.info("Cluster: %d cluster(s), %d noise", n_clusters, n_noise)

    return {
        "clusters": result_clusters,
        "noise": noise,
        "n_clusters": n_clusters,
        "n_noise": n_noise,
    }
