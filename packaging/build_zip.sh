#!/usr/bin/env bash
# Build the distributable zip: nidra-<version>.zip — install.sh, install.cmd,
# runtime/nidra. Pure stdlib, so the runtime is just the package itself.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 -c "import re; print(re.search(r'__version__ = \"(.*)\"', open('$ROOT/nidra/__init__.py').read()).group(1))")"
OUT="$ROOT/dist"
STAGE="$(mktemp -d)/nidra-$VERSION"

mkdir -p "$STAGE/runtime" "$OUT"
cp -R "$ROOT/nidra" "$STAGE/runtime/nidra"
find "$STAGE" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
cp "$ROOT/packaging/install.sh" "$ROOT/packaging/install.cmd" "$STAGE/"
cp "$ROOT/packaging/USER-GUIDE.md" "$STAGE/"
chmod +x "$STAGE/install.sh"

(cd "$(dirname "$STAGE")" && zip -qr "$OUT/nidra-$VERSION.zip" "nidra-$VERSION")
echo "built $OUT/nidra-$VERSION.zip ($(du -h "$OUT/nidra-$VERSION.zip" | cut -f1))"
