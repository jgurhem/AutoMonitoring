#!/bin/sh

docker exec -it monia psql -U monia -d monia
# docker exec -it monia pg_dump -U monia -d monia
