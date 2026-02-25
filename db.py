import psycopg2
import os
import json
from pgvector.psycopg2 import register_vector

def get_connection():
    conn = psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )
    register_vector(conn)
    return conn

def is_recently_collected(url: str) -> bool:
    query = """
    SELECT 1 FROM documents
    WHERE url = %(url)s
    AND collected_at >= NOW() - INTERVAL '1 month'
    LIMIT 1;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"url": url})
            return cur.fetchone() is not None
    conn.close()

def insert_document(doc: dict):
    query = """
    INSERT INTO documents (
        id, source, title, authors, url, description, content,
        categories, language, stars,
        published_at, updated_at, collected_at, raw
    )
    VALUES (
        %(id)s, %(source)s, %(title)s, %(authors)s, %(url)s, %(description)s, %(content)s,
        %(categories)s, %(language)s, %(stars)s,
        %(published_at)s, %(updated_at)s, %(collected_at)s, %(raw)s
    )
    ON CONFLICT (id) DO UPDATE SET
        title = EXCLUDED.title,
        authors = EXCLUDED.authors,
        url = EXCLUDED.url,
        description = EXCLUDED.description,
        content = EXCLUDED.content,
        categories = EXCLUDED.categories,
        language = EXCLUDED.language,
        stars = EXCLUDED.stars,
        published_at = EXCLUDED.published_at,
        updated_at = EXCLUDED.updated_at,
        collected_at = EXCLUDED.collected_at,
        raw = EXCLUDED.raw;
    """

    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {
                "id": doc.get("id"),
                "source": doc.get("source"),
                "title": doc.get("title"),
                "authors": doc.get("authors"),
                "url": doc.get("url"),
                "description": doc.get("description"),
                "content": doc.get("content"),
                "categories": doc.get("categories"),
                "language": doc.get("language"),
                "stars": doc.get("stars"),
                "published_at": doc.get("published"),
                "updated_at": doc.get("updated_at"),
                "collected_at": doc.get("collected_at"),
                "raw": json.dumps(doc)
            })
    conn.close()

def fetch_documents_without_embeddings(batch_size: int = 100) -> list[dict]:
    query = """
    SELECT id, title, description, content
    FROM documents
    WHERE embedding IS NULL
    ORDER BY collected_at DESC
    LIMIT %(batch_size)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"batch_size": batch_size})
            rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "description": r[2], "content": r[3]}
        for r in rows
    ]

def save_embedding(doc_id: str, embedding: list[float]):
    import numpy as np
    query = """
    UPDATE documents SET embedding = %(embedding)s WHERE id = %(id)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"id": doc_id, "embedding": np.array(embedding)})
    conn.close()

def fetch_near_duplicates(threshold: float = 0.95) -> list[dict]:
    query = """
    SELECT DISTINCT ON (LEAST(d1.id, d2.id), GREATEST(d1.id, d2.id))
        d1.id AS id1, d1.title AS title1, d2.id AS id2, d2.title AS title2,
        1 - (d1.embedding <=> d2.embedding) AS similarity
    FROM documents d1
    CROSS JOIN LATERAL (
        SELECT id, title, embedding
        FROM documents d2
        WHERE d2.id != d1.id
        ORDER BY d1.embedding <=> d2.embedding
        LIMIT 1
    ) d2
    WHERE 1 - (d1.embedding <=> d2.embedding) > %(threshold)s
    ORDER BY LEAST(d1.id, d2.id), GREATEST(d1.id, d2.id), similarity DESC;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"threshold": threshold})
            rows = cur.fetchall()
    conn.close()
    return [
        {"id1": r[0], "title1": r[1], "id2": r[2], "title2": r[3], "similarity": r[4]}
        for r in rows
    ]

def fetch_novelty_scores() -> list[dict]:
    query = """
    SELECT d1.id, d1.title,
        1 - (
            SELECT d2.embedding <=> d1.embedding
            FROM documents d2
            WHERE d2.id != d1.id
            ORDER BY d2.embedding <=> d1.embedding
            LIMIT 1
        ) AS nearest_similarity
    FROM documents d1
    WHERE d1.embedding IS NOT NULL;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "nearest_similarity": r[2]}
        for r in rows
    ]

def fetch_documents(since, source=None, has_embedding=None, search=None, limit=500) -> list[tuple]:
    conds = ["collected_at >= %(since)s"]
    params = {"since": since, "limit": limit}

    if source:
        conds.append("source = %(source)s")
        params["source"] = source
    if has_embedding is True:
        conds.append("embedding IS NOT NULL")
    elif has_embedding is False:
        conds.append("embedding IS NULL")
    if search:
        conds.append("title ILIKE %(search)s")
        params["search"] = f"%{search}%"

    where = " AND ".join(conds)
    query = f"""
    SELECT id, source, title, published_at, url,
           embedding IS NOT NULL AS has_emb
    FROM documents
    WHERE {where}
    ORDER BY published_at DESC
    LIMIT %(limit)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    conn.close()


def fetch_document(doc_id: str) -> tuple | None:
    query = """
    SELECT title, authors, url, description, content, categories, published_at
    FROM documents WHERE id = %(id)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"id": doc_id})
            return cur.fetchone()
    conn.close()


def fetch_counts() -> dict:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents;")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;")
            with_emb = cur.fetchone()[0]
            cur.execute("SELECT source, COUNT(*) FROM documents GROUP BY source ORDER BY count DESC;")
            by_source = cur.fetchall()
    conn.close()
    return {"total": total, "with_embedding": with_emb, "by_source": by_source}


def fetch_daily_counts(days: int = 30) -> list[tuple]:
    query = """
    SELECT DATE(collected_at) AS day, source, COUNT(*)
    FROM documents
    WHERE collected_at >= NOW() - INTERVAL '1 day' * %(days)s
    GROUP BY day, source
    ORDER BY day;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"days": days})
            return cur.fetchall()
    conn.close()


def fetch_arxiv_categories(limit: int = 20) -> list[tuple]:
    query = """
    SELECT unnest(categories) AS cat, COUNT(*) AS n
    FROM documents
    WHERE source = 'arxiv'
    GROUP BY cat
    ORDER BY n DESC
    LIMIT %(limit)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"limit": limit})
            return cur.fetchall()
    conn.close()


def search_similar(vec, top_k: int = 10) -> list[tuple]:
    import numpy as np
    query = """
    SELECT id, source, title, url, published_at,
           1 - (embedding <=> %(vec)s) AS similarity
    FROM documents
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> %(vec)s
    LIMIT %(k)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"vec": np.array(vec), "k": top_k})
            return cur.fetchall()
    conn.close()


def fetch_all_embeddings() -> list[dict]:
    import numpy as np
    query = """
    SELECT id, title, embedding, published_at
    FROM documents
    WHERE embedding IS NOT NULL;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "embedding": np.array(r[2]), "published_at": r[3]}
        for r in rows
    ]