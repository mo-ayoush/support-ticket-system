#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/lambdas"
rm -rf "$OUT"
mkdir -p "$OUT"
for name in idempotency write read notification_worker; do
  mkdir -p "$OUT/$name"
  cp "$ROOT/lambdas/$name/app.py" "$ROOT/lambdas/shared/common.py" "$OUT/$name/"
  (cd "$OUT/$name" && zip -q -r "$OUT/$name.zip" .)
done
echo "Lambda packages created in $OUT"
