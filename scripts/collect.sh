#!/bin/sh

cd "$(dirname "$0")/.."

export PG_HOST=localhost
export PG_PORT=5432
export PG_DB=monia
export PG_USER=monia
export PG_PASSWORD=monia

set -e

. venv/bin/activate
python collect.py
