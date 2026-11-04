#!/usr/bin/env bash
# Runs when a submission is opened, reopened or edited.
# Needs BODY, NUMBER, GH_TOKEN and GH_REPO in the environment.
# MODE=recheck is used by recheck_all.sh: a valid verified map stays verified instead of going back to pending.
set -uo pipefail
here="$(dirname "${BASH_SOURCE[0]}")"
source "$here/common.sh"

labels=$(current_labels)
# A rejected submission is a moderator decision; do not touch it.
if has_label rejected "$labels"; then
  exit 0
fi
was_verified=false
has_label verified "$labels" && was_verified=true

errors=$(python3 "$validate_script" fields)
if [[ -n "$errors" ]]; then
  mark_invalid "$errors"
  exit 0
fi

url=$(python3 "$validate_script" url)
temp=$(mktemp)
body_file=$(mktemp)
trap 'rm -f "$temp" "$body_file"' EXIT

content_type=$(curl --silent --show-error --fail --location --max-time 300 --max-filesize 536870912 \
  --proto '=https' --proto-redir '=https' --output "$temp" --write-out '%{content_type}' "$url") || {
  mark_invalid "The download URL could not be downloaded. Make sure it is a direct HTTPS link that works without signing in and that the file is smaller than 512 MB."
  exit 0
}
if (( $(stat -c '%s' "$temp") > 536870912 )); then
  mark_invalid "The file is larger than the 512 MB limit."
  exit 0
fi
if [[ "$content_type" == text/html* ]]; then
  mark_invalid "The download URL points to a web page, not directly to the file. Use a direct link, for example a GitHub Releases asset."
  exit 0
fi

errors=$(python3 "$validate_script" archive "$temp")
hash=$(sha256sum "$temp" | awk '{print toupper($1)}')

duplicates=$(open_issues_mentioning "$url")
[[ -n "$duplicates" ]] && errors+=$'\n'"The same download URL is already used by $duplicates."
duplicates=$(open_issues_mentioning "$hash")
[[ -n "$duplicates" ]] && errors+=$'\n'"A file with the same SHA-256 was already submitted in $duplicates."

errors=$(without_blank_lines "$errors")
if [[ -n "$errors" ]]; then
  mark_invalid "$errors"
  exit 0
fi

echo "RESULT=valid"
if [[ "${MODE:-normal}" == recheck && "$was_verified" == true ]]; then
  exit 0
fi

# Everything passed: back to the moderation queue, with the SHA-256 of the current file.
set_status pending
if [[ "$(python3 "$validate_script" sha | tr 'a-f' 'A-F')" != "$hash" ]]; then
  gh issue view "$NUMBER" --repo "$GH_REPO" --json body --jq .body > "$body_file"
  HASH="$hash" perl -0pi -e 's/(### SHA-256 \(generated automatically\)\s*)(?:_No response_|[^\s]+)?/$1.$ENV{HASH}/e' "$body_file"
  gh issue edit "$NUMBER" --repo "$GH_REPO" --body-file "$body_file"
fi
if [[ "$was_verified" == true && "${MODE:-normal}" != recheck ]]; then
  gh issue comment "$NUMBER" --repo "$GH_REPO" --body "This submission changed after verification and requires review again."
fi
