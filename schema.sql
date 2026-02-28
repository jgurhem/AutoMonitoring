CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,               -- rss | arxiv | github
    title TEXT,
    authors TEXT[],
    url TEXT,
    description TEXT,
    content TEXT,
    categories TEXT[],
    language TEXT,
    stars INTEGER,
    published_at TIMESTAMP,
    updated_at TIMESTAMP,
    collected_at TIMESTAMP NOT NULL,
    raw JSONB,
    embedding vector(384),
    summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_collected_at ON documents(collected_at);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    pref_novelty_threshold FLOAT DEFAULT 0.6,
    pref_digest_days INTEGER DEFAULT 7,
    pref_digest_novelty_threshold FLOAT
);

CREATE TABLE IF NOT EXISTS rss_feeds (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS arxiv_searches (
    id SERIAL PRIMARY KEY,
    query TEXT UNIQUE NOT NULL,
    max_results INTEGER DEFAULT 10,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_rss_feeds (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    feed_id INTEGER REFERENCES rss_feeds(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, feed_id)
);

CREATE TABLE IF NOT EXISTS user_arxiv_searches (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    search_id INTEGER REFERENCES arxiv_searches(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, search_id)
);

CREATE TABLE IF NOT EXISTS user_documents (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    read_at TIMESTAMP,
    PRIMARY KEY (user_id, document_id)
);

CREATE TABLE IF NOT EXISTS user_favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, document_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_document_tags (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, document_id, tag_id)
);