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
    raw JSONB
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_collected_at ON documents(collected_at);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);