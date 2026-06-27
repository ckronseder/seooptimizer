#!/bin/sh
set -e

mkdir -p /app/data /app/chroma_db
chown -R appuser:appuser /app/data /app/chroma_db

exec su -s /bin/sh appuser -c "exec $*"
