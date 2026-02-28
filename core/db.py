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

def fetch_documents_without_summary(batch_size: int = 10) -> list[dict]:
    query = """
    SELECT id, title, description, content
    FROM documents
    WHERE summary IS NULL
    AND (description IS NOT NULL OR content IS NOT NULL)
    ORDER BY collected_at DESC
    LIMIT %(batch_size)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"batch_size": batch_size})
            rows = cur.fetchall()
    return [
        {"id": r[0], "title": r[1], "description": r[2], "content": r[3]}
        for r in rows
    ]

def save_summary(doc_id: str, summary: str):
    query = "UPDATE documents SET summary = %(summary)s WHERE id = %(id)s;"
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, {"id": doc_id, "summary": summary})

def fetch_summaries_since(published_since: int, novelty_threshold: float | None = None, user_id: int | None = None) -> list[dict]:
    conds = [
        "d1.summary IS NOT NULL",
        "d1.published_at >= NOW() - INTERVAL '1 day' * %(published_since)s",
    ]
    if novelty_threshold is not None:
        conds.append("d1.embedding IS NOT NULL")

    join = "JOIN user_documents ud ON ud.document_id = d1.id AND ud.user_id = %(user_id)s" if user_id is not None else ""
    where = " AND ".join(conds)
    query = f"""
    SELECT d1.id, d1.title, d1.summary,
        1 - (
            SELECT d2.embedding <=> d1.embedding
            FROM documents d2
            WHERE d2.id != d1.id AND d2.embedding IS NOT NULL
            ORDER BY d2.embedding <=> d1.embedding
            LIMIT 1
        ) AS novelty_score
    FROM documents d1
    {join}
    WHERE {where}
    ORDER BY d1.published_at DESC;
    """
    params = {"published_since": published_since}
    if user_id is not None:
        params["user_id"] = user_id
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    docs = [{"id": r[0], "title": r[1], "summary": r[2], "novelty_score": r[3]} for r in rows]
    if novelty_threshold is not None:
        docs = [d for d in docs if d["novelty_score"] is not None and d["novelty_score"] > novelty_threshold]
    return docs


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
    return [
        {"id1": r[0], "title1": r[1], "id2": r[2], "title2": r[3], "similarity": r[4]}
        for r in rows
    ]

def fetch_novelty_scores(
    published_since: int | None = None,
    collected_since: int | None = None,
    updated_since: int | None = None,
    user_id: int | None = None,
) -> list[dict]:
    conds = ["d1.embedding IS NOT NULL"]
    params = {}
    if published_since is not None:
        conds.append("d1.published_at >= NOW() - INTERVAL '1 day' * %(published_since)s")
        params["published_since"] = published_since
    if collected_since is not None:
        conds.append("d1.collected_at >= NOW() - INTERVAL '1 day' * %(collected_since)s")
        params["collected_since"] = collected_since
    if updated_since is not None:
        conds.append("d1.updated_at >= NOW() - INTERVAL '1 day' * %(updated_since)s")
        params["updated_since"] = updated_since
    join = ""
    if user_id is not None:
        join = "JOIN user_documents ud ON ud.document_id = d1.id AND ud.user_id = %(user_id)s"
        params["user_id"] = user_id

    where = " AND ".join(conds)
    query = f"""
    SELECT d1.id, d1.title,
        1 - (
            SELECT d2.embedding <=> d1.embedding
            FROM documents d2
            WHERE d2.id != d1.id
            ORDER BY d2.embedding <=> d1.embedding
            LIMIT 1
        ) AS nearest_similarity
    FROM documents d1
    {join}
    WHERE {where};
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return [
        {"id": r[0], "title": r[1], "nearest_similarity": r[2]}
        for r in rows
    ]


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


def fetch_all_embeddings(user_id: int | None = None) -> list[dict]:
    import numpy as np
    if user_id is not None:
        query = """
        SELECT d.id, d.title, d.embedding, d.published_at
        FROM documents d
        JOIN user_documents ud ON d.id = ud.document_id
        WHERE d.embedding IS NOT NULL AND ud.user_id = %(user_id)s;
        """
        params = {"user_id": user_id}
    else:
        query = """
        SELECT id, title, embedding, published_at
        FROM documents
        WHERE embedding IS NOT NULL;
        """
        params = {}
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    return [
        {"id": r[0], "title": r[1], "embedding": np.array(r[2]), "published_at": r[3]}
        for r in rows
    ]


# ─── Users ───────────────────────────────────────────────────────────────────

def get_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, is_admin, is_active, "
                "pref_novelty_threshold, pref_digest_days, pref_digest_novelty_threshold "
                "FROM users WHERE username = %(username)s;",
                {"username": username},
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "username": row[1], "password_hash": row[2],
        "is_admin": row[3], "is_active": row[4],
        "pref_novelty_threshold": row[5], "pref_digest_days": row[6],
        "pref_digest_novelty_threshold": row[7],
    }


def create_user(username: str, password_hash: str, is_admin: bool = False) -> int:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (%(u)s, %(h)s, %(a)s) RETURNING id;",
                {"u": username, "h": password_hash, "a": is_admin},
            )
            user_id = cur.fetchone()[0]
    return user_id


def get_all_users() -> list[dict]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, is_admin, is_active, created_at FROM users ORDER BY id;"
            )
            rows = cur.fetchall()
    return [
        {"id": r[0], "username": r[1], "is_admin": r[2], "is_active": r[3], "created_at": r[4]}
        for r in rows
    ]


def set_user_active(user_id: int, active: bool):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_active = %(a)s WHERE id = %(id)s;",
                {"id": user_id, "a": active},
            )


def update_user_password(user_id: int, password_hash: str):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %(h)s WHERE id = %(id)s;",
                {"id": user_id, "h": password_hash},
            )


def update_user_prefs(user_id: int, **prefs):
    allowed = {
        "pref_novelty_threshold", "pref_digest_days",
        "pref_digest_novelty_threshold",
    }
    updates = {k: v for k, v in prefs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["user_id"] = user_id
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE users SET {set_clause} WHERE id = %(user_id)s;", updates)


# ─── Feed / search catalog ────────────────────────────────────────────────────

def get_or_create_rss_feed(url: str, name: str | None = None) -> int:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM rss_feeds WHERE url = %(url)s;", {"url": url})
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO rss_feeds (url, name) VALUES (%(url)s, %(name)s) RETURNING id;",
                {"url": url, "name": name},
            )
            return cur.fetchone()[0]


def get_or_create_arxiv_search(query: str, max_results: int = 10) -> int:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM arxiv_searches WHERE query = %(q)s;", {"q": query})
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO arxiv_searches (query, max_results) VALUES (%(q)s, %(m)s) RETURNING id;",
                {"q": query, "m": max_results},
            )
            return cur.fetchone()[0]


def get_all_rss_feeds() -> list[dict]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, url, name, created_at FROM rss_feeds ORDER BY id;")
            rows = cur.fetchall()
    return [{"id": r[0], "url": r[1], "name": r[2], "created_at": r[3]} for r in rows]


def get_all_arxiv_searches() -> list[dict]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, query, max_results, created_at FROM arxiv_searches ORDER BY id;")
            rows = cur.fetchall()
    return [{"id": r[0], "query": r[1], "max_results": r[2], "created_at": r[3]} for r in rows]


# ─── User subscriptions ───────────────────────────────────────────────────────

def get_user_rss_feeds(user_id: int) -> list[dict]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.url, f.name FROM rss_feeds f "
                "JOIN user_rss_feeds uf ON f.id = uf.feed_id "
                "WHERE uf.user_id = %(uid)s ORDER BY f.id;",
                {"uid": user_id},
            )
            rows = cur.fetchall()
    return [{"feed_id": r[0], "url": r[1], "name": r[2]} for r in rows]


def subscribe_user_to_feed(user_id: int, feed_id: int):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_rss_feeds (user_id, feed_id) VALUES (%(uid)s, %(fid)s) ON CONFLICT DO NOTHING;",
                {"uid": user_id, "fid": feed_id},
            )


def unsubscribe_user_from_feed(user_id: int, feed_id: int):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_rss_feeds WHERE user_id = %(uid)s AND feed_id = %(fid)s;",
                {"uid": user_id, "fid": feed_id},
            )


def get_user_arxiv_searches(user_id: int) -> list[dict]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.id, s.query, s.max_results FROM arxiv_searches s "
                "JOIN user_arxiv_searches us ON s.id = us.search_id "
                "WHERE us.user_id = %(uid)s ORDER BY s.id;",
                {"uid": user_id},
            )
            rows = cur.fetchall()
    return [{"search_id": r[0], "query": r[1], "max_results": r[2]} for r in rows]


def subscribe_user_to_search(user_id: int, search_id: int):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_arxiv_searches (user_id, search_id) VALUES (%(uid)s, %(sid)s) ON CONFLICT DO NOTHING;",
                {"uid": user_id, "sid": search_id},
            )


def unsubscribe_user_from_search(user_id: int, search_id: int):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_arxiv_searches WHERE user_id = %(uid)s AND search_id = %(sid)s;",
                {"uid": user_id, "sid": search_id},
            )


def get_all_rss_feeds_with_subscribers() -> list[dict]:
    """Returns feeds that have at least one subscriber, with their subscriber_ids list."""
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.url, array_agg(uf.user_id) AS subscriber_ids "
                "FROM rss_feeds f JOIN user_rss_feeds uf ON f.id = uf.feed_id "
                "GROUP BY f.id, f.url;"
            )
            rows = cur.fetchall()
    return [{"feed_id": r[0], "url": r[1], "subscriber_ids": r[2]} for r in rows]


def get_all_arxiv_searches_with_subscribers() -> list[dict]:
    """Returns searches that have at least one subscriber, with their subscriber_ids list."""
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.id, s.query, s.max_results, array_agg(us.user_id) AS subscriber_ids "
                "FROM arxiv_searches s JOIN user_arxiv_searches us ON s.id = us.search_id "
                "GROUP BY s.id, s.query, s.max_results;"
            )
            rows = cur.fetchall()
    return [{"search_id": r[0], "query": r[1], "max_results": r[2], "subscriber_ids": r[3]} for r in rows]


# ─── User-document links ──────────────────────────────────────────────────────

def link_document_to_user(user_id: int, doc_id: str):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_documents (user_id, document_id) VALUES (%(uid)s, %(did)s) ON CONFLICT DO NOTHING;",
                {"uid": user_id, "did": doc_id},
            )


def fetch_documents_for_user(user_id: int, since, source=None, search=None, limit=500) -> list[tuple]:
    conds = ["ud.user_id = %(user_id)s", "d.collected_at >= %(since)s"]
    params = {"user_id": user_id, "since": since, "limit": limit}

    if source:
        conds.append("d.source = %(source)s")
        params["source"] = source
    if search:
        conds.append("d.title ILIKE %(search)s")
        params["search"] = f"%{search}%"

    where = " AND ".join(conds)
    query = f"""
    SELECT d.id, d.source, d.title, d.published_at, d.url
    FROM documents d
    JOIN user_documents ud ON d.id = ud.document_id
    WHERE {where}
    ORDER BY d.published_at DESC
    LIMIT %(limit)s;
    """
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


# ─── Favorites & tags ─────────────────────────────────────────────────────────

def add_favorite(user_id: int, doc_id: str):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_favorites (user_id, document_id) VALUES (%(uid)s, %(did)s) ON CONFLICT DO NOTHING;",
                {"uid": user_id, "did": doc_id},
            )


def remove_favorite(user_id: int, doc_id: str):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_favorites WHERE user_id = %(uid)s AND document_id = %(did)s;",
                {"uid": user_id, "did": doc_id},
            )


def update_favorite_note(user_id: int, doc_id: str, note: str):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_favorites SET note = %(note)s WHERE user_id = %(uid)s AND document_id = %(did)s;",
                {"uid": user_id, "did": doc_id, "note": note},
            )


def get_user_favorites(user_id: int) -> list[dict]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT d.id, d.source, d.title, d.published_at, d.url, uf.note, uf.created_at "
                "FROM documents d JOIN user_favorites uf ON d.id = uf.document_id "
                "WHERE uf.user_id = %(uid)s ORDER BY uf.created_at DESC;",
                {"uid": user_id},
            )
            rows = cur.fetchall()
    return [
        {"id": r[0], "source": r[1], "title": r[2], "published_at": r[3],
         "url": r[4], "note": r[5], "favorited_at": r[6]}
        for r in rows
    ]


def is_favorite(user_id: int, doc_id: str) -> bool:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM user_favorites WHERE user_id = %(uid)s AND document_id = %(did)s;",
                {"uid": user_id, "did": doc_id},
            )
            return cur.fetchone() is not None


def get_tags() -> list[dict]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM tags ORDER BY name;")
            rows = cur.fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]


def create_tag(name: str) -> int:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tags (name) VALUES (%(name)s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id;",
                {"name": name},
            )
            return cur.fetchone()[0]


def tag_document(user_id: int, doc_id: str, tag_id: int):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_document_tags (user_id, document_id, tag_id) VALUES (%(uid)s, %(did)s, %(tid)s) ON CONFLICT DO NOTHING;",
                {"uid": user_id, "did": doc_id, "tid": tag_id},
            )


def untag_document(user_id: int, doc_id: str, tag_id: int):
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_document_tags WHERE user_id = %(uid)s AND document_id = %(did)s AND tag_id = %(tid)s;",
                {"uid": user_id, "did": doc_id, "tid": tag_id},
            )


def get_document_tags(user_id: int, doc_id: str) -> list[str]:
    conn = get_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.name FROM tags t JOIN user_document_tags udt ON t.id = udt.tag_id "
                "WHERE udt.user_id = %(uid)s AND udt.document_id = %(did)s ORDER BY t.name;",
                {"uid": user_id, "did": doc_id},
            )
            rows = cur.fetchall()
    return [r[0] for r in rows]