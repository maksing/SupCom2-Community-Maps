#!/usr/bin/env bash
# Re-downloads every verified map. A map whose download stops working becomes broken, and a map whose file
# changed after it was verified goes back to pending. Needs GH_TOKEN and GH_REPO in the environment.
set -uo pipefail
here="$(dirname "${BASH_SOURCE[0]}")"

numbers=$(gh issue list --repo "$GH_REPO" --state open --label verified --limit 500 --json number --jq '.[].number')
temp=$(mktemp)
trap 'rm -f "$temp"' EXIT

while read -r number; do
  [[ -n "$number" ]] || continue
  export NUMBER="$number"
  BODY=$(gh issue view "$number" --repo "$GH_REPO" --json body --jq .body)
  export BODY
  source "$here/common.sh"
  url=$(python3 "$validate_script" url)
  expected=$(python3 "$validate_script" sha | tr 'a-f' 'A-F')
  [[ -n "$url" ]] || continue

  if ! curl --silent --show-error --fail --location --max-time 300 --max-filesize 536870912 \
       --proto '=https' --proto-redir '=https' --output "$temp" "$url"; then
    echo "#$number: download failed"
    set_status broken
    gh issue comment "$number" --repo "$GH_REPO" --body "The weekly check could not download this map, so the verified label was removed and the issue was labeled broken. Fix the download URL (edit the issue) and it will be checked again."
    continue
  fi

  actual=$(sha256sum "$temp" | awk '{print toupper($1)}')
  if [[ -n "$expected" && "$actual" != "$expected" ]]; then
    echo "#$number: file changed"
    set_status pending
    gh issue comment "$number" --repo "$GH_REPO" --body "The weekly check found that the file behind the download URL changed after this map was verified (SHA-256 was \`$expected\`, now \`$actual\`). The verified label was removed; edit the issue to submit the new file and a moderator will review it again."
  else
    echo "#$number: ok"
  fi
done <<< "$numbers"
