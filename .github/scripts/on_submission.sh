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
  set_collision false
  mark_invalid "$errors"
  exit 0
fi

url=$(python3 "$validate_script" url)
temp=$(mktemp)
body_file=$(mktemp)
scenarios_file=$(mktemp)
trap 'rm -f "$temp" "$body_file" "$scenarios_file"' EXIT

content_type=$(curl --silent --show-error --fail --location --max-time 300 --max-filesize 536870912 \
  --proto '=https' --proto-redir '=https' --output "$temp" --write-out '%{content_type}' "$url") || {
  set_collision false
  mark_invalid "The download URL could not be downloaded. Make sure it is a direct HTTPS link that works without signing in and that the file is smaller than 512 MB."
  exit 0
}
if (( $(stat -c '%s' "$temp") > 536870912 )); then
  set_collision false
  mark_invalid "The file is larger than the 512 MB limit."
  exit 0
fi
if [[ "$content_type" == text/html* ]]; then
  set_collision false
  mark_invalid "The download URL points to a web page, not directly to the file. Use a direct link, for example a GitHub Releases asset."
  exit 0
fi

errors=$(python3 "$validate_script" archive "$temp")
# The scenario paths are read from the file itself (root maps folder). Whatever the author typed into the
# field is replaced, and the collision check below works on the generated paths.
original_paths=$(python3 "$validate_script" paths)
python3 "$validate_script" scenarios "$temp" > "$scenarios_file"
new_paths=$(cat "$scenarios_file")
BODY=$(python3 "$validate_script" set-scenarios "$scenarios_file")
export BODY

# Of two verified maps that share a scenario path the older one keeps its status when everything is rechecked.
if [[ "${MODE:-normal}" == recheck && "$was_verified" == true ]]; then
  collisions=$(scenario_collisions --newer-only)
else
  collisions=$(scenario_collisions)
fi
if [[ -n "$collisions" ]]; then
  errors+=$'\n'"$collisions"
  set_collision true
else
  set_collision false
fi
hash=$(sha256sum "$temp" | awk '{print toupper($1)}')
md5=$(md5sum "$temp" | awk '{print toupper($1)}')

# A verified map must not change silently: the weekly check and the recheck report a changed file.
existing_sha=$(python3 "$validate_script" sha | tr 'a-f' 'A-F')
if [[ "${MODE:-normal}" == recheck && "$was_verified" == true && -n "$existing_sha" && "$existing_sha" != "$hash" ]]; then
  errors+=$'\n'"The file changed after the map was verified (SHA-256 was $existing_sha, now $hash)."
fi

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

# A verified map that is rechecked keeps its status and its SHA-256; every other valid submission goes
# (back) to the moderation queue with the hashes of the current file.
keep_sha=""
if [[ "${MODE:-normal}" == recheck && "$was_verified" == true ]]; then
  keep_sha="--keep-sha"
else
  set_status pending
fi

existing_md5=$(python3 "$validate_script" md5 | tr 'a-f' 'A-F')
if [[ -z "$existing_sha" || "$existing_md5" != "$md5" || "$original_paths" != "$new_paths" \
      || ( -z "$keep_sha" && "$existing_sha" != "$hash" ) ]]; then
  live_body=$(gh issue view "$NUMBER" --repo "$GH_REPO" --json body --jq .body)
  BODY="$live_body" python3 "$validate_script" hashes "$hash" "$md5" $keep_sha > "$body_file"
  BODY=$(cat "$body_file") python3 "$validate_script" set-scenarios "$scenarios_file" > "$body_file.new"
  mv "$body_file.new" "$body_file"
  gh issue edit "$NUMBER" --repo "$GH_REPO" --body-file "$body_file"
fi

# Tell the author that the check passed (not when everything is rechecked, which would comment on every map).
if [[ "${MODE:-normal}" != recheck ]]; then
  message="The map passed the automatic check:"$'\n\n'
  message+="- the file name follows the naming convention and matches the version and player count"$'\n'
  message+="- the file downloads, is a valid archive without forbidden files, and has scenario files in the root maps folder"$'\n'
  message+="- the scenario paths are not used by another verified map, and the download is not a duplicate"$'\n\n'
  message+="Scenario File Paths (read from the file):"$'\n\n'"$(bullet_list "$new_paths")"$'\n'
  message+="SHA-256: \`$hash\`"$'\n'"MD5: \`$md5\`"$'\n\n'
  if [[ "$was_verified" == true ]]; then
    message+="The map was verified before, but it changed, so a moderator has to review it again."
  else
    message+="A moderator will review it next."
  fi
  gh issue comment "$NUMBER" --repo "$GH_REPO" --body "$message"
fi
