#!/bin/sh

cd "$(dirname "$0")/.."

docker run -d \
  --name monia \
  -e POSTGRES_USER=monia \
  -e POSTGRES_PASSWORD=monia \
  -e POSTGRES_DB=monia \
  -p 5432:5432 \
  -v "$(pwd)/monia_data":/var/lib/postgresql \
  -v "$(pwd)/schema.sql":/docker-entrypoint-initdb.d/schema.sql \
  pgvector/pgvector:pg18
