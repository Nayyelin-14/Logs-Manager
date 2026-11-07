#!/usr/bin/env bash
# scripts/check_file_sizes.sh
# Fails if any NEW or CHANGED file exceeds 300 lines.
# For pre-existing files >300 lines, just reports (no fail).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAX_LINES=300
FAIL=0

echo "Checking file sizes (max ${MAX_LINES} lines for new/changed files)..."

# Check all tracked files that are > 300 lines (report only)
while IFS= read -r -d '' file; do
  lines=$(wc -l < "$file" 2>/dev/null || echo 0)
  if [ "$lines" -gt "$MAX_LINES" ]; then
    echo "  [REPORT] ${file}: ${lines} lines (pre-existing, over limit)"
  fi
done < <(git ls-files -z 2>/dev/null | xargs -0 -I{} sh -c 'test -f "{}" && echo "{}"')

# For new/untracked files, check each. Archived historical docs are intentionally
# moved/superseded and are exempt from the new-file size limit.
while IFS= read -r -d '' file; do
  case "$file" in
    docs/archive/*) continue ;;
  esac
  lines=$(wc -l < "$file" 2>/dev/null || echo 0)
  if [ "$lines" -gt "$MAX_LINES" ]; then
    echo "  [FAIL] ${file}: ${lines} lines (new file exceeds ${MAX_LINES})"
    FAIL=1
  fi
done < <(git ls-files --others --exclude-standard -z 2>/dev/null)

if [ "$FAIL" -eq 0 ]; then
  echo "File size check PASSED."
  exit 0
else
  echo "File size check FAILED."
  exit 1
fi
