import psycopg2
import os
import json

def get_connection():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )

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
    ON CONFLICT (id) DO NOTHING;
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