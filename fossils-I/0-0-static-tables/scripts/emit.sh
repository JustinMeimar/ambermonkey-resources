#!/usr/bin/env bash
# Copy source/<FOSSIL_TABLE_NAME>.json into $1. The static-tables fossil
# uses a single shared emitter so adding a new hand-authored table only
# needs a source file + a [tables.<name>] entry.
set -euo pipefail

if [[ -z "${FOSSIL_TABLE_NAME:-}" ]]; then
  echo "emit.sh: FOSSIL_TABLE_NAME is not set" >&2
  exit 1
fi

src="$(dirname "$0")/../source/${FOSSIL_TABLE_NAME}.json"
if [[ ! -f "$src" ]]; then
  echo "emit.sh: no source file at $src" >&2
  exit 1
fi

cp "$src" "$1"
