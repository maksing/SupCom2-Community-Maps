#!/usr/bin/env bash
# Builds the catalog JSON files from the verified issues and commits them to the catalog branch.
# Needs GH_REPO and GH_TOKEN. CATALOG_REMOTE overrides the git remote (used by the tests),
# BUILD_ARGS overrides the build command arguments (default: --fetch).
# The branch only ever gets a commit when the files changed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
branch="${CATALOG_BRANCH:-catalog}"
remote="${CATALOG_REMOTE:-https://x-access-token:${GH_TOKEN:-}@github.com/${GH_REPO}.git}"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

python3 "$here/build_catalog.py" ${BUILD_ARGS:---fetch} "$work/out"

if git ls-remote --exit-code --heads "$remote" "$branch" > /dev/null 2>&1; then
  git clone --quiet --depth 1 --branch "$branch" "$remote" "$work/repo"
else
  git init --quiet "$work/repo"
  git -C "$work/repo" checkout --quiet -b "$branch"
  git -C "$work/repo" remote add origin "$remote"
fi

cp "$work/out/maps.json" "$work/out/community-maps.json" "$work/repo/"
cat > "$work/repo/README.md" <<'README'
# Map catalog

This branch is generated automatically from the verified issues of the main branch's repository. Do not edit it by hand.

- `maps.json`: official maps (issues labeled `verified` and `promoted`)
- `community-maps.json`: community maps (issues labeled `verified`, not `promoted`)

Maps that also carry the `hidden` label are not listed.
README

cd "$work/repo"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "The catalog is unchanged."
  exit 0
fi
git commit --quiet -m "Update catalog from verified issues"
git push --quiet origin "$branch"
echo "The catalog was updated."
