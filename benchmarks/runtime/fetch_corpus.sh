#!/usr/bin/env bash
# Fetch the foreign corpus used by the runtime end-to-end harness.
#
# The corpus is NOT vendored into PAW. Vendoring would put 1.5 MB of
# third-party code PAW does not own into its tree, and it would destroy the
# provenance that matters: that the measured bytes are exactly some upstream
# commit. Instead it is cloned and checked out at a pinned revision, and the
# harness records the revision it actually ran against.
set -euo pipefail

CORPUS_URL="${CORPUS_URL:-https://github.com/life4/textdistance.git}"
CORPUS_REV="${CORPUS_REV:-d6a68d6}"
DEST="${1:-/tmp/paw-e2e/textdistance}"

if [ -d "$DEST/.git" ]; then
  echo "corpus already present at $DEST"
else
  git clone --quiet "$CORPUS_URL" "$DEST"
fi

git -C "$DEST" fetch --quiet origin "$CORPUS_REV" 2>/dev/null || true
git -C "$DEST" checkout --quiet --detach "$CORPUS_REV"

actual="$(git -C "$DEST" rev-parse --short HEAD)"
if [ "$actual" != "$CORPUS_REV" ]; then
  echo "FATAL: checked out $actual but pinned revision is $CORPUS_REV" >&2
  exit 1
fi
git -C "$DEST" reset --quiet --hard "$CORPUS_REV"

echo "corpus ready: $DEST @ $actual (clean)"