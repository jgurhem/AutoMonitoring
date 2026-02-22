#!/bin/sh

docker run -d \
  --name monia \
  -e POSTGRES_USER=monia \
  -e POSTGRES_PASSWORD=monia \
  -e POSTGRES_DB=monia \
  -p 5432:5432 \
  -v "$(pwd)/monia_data":/var/lib/postgresql/data \
  postgres:15