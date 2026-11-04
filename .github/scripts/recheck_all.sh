#!/usr/bin/env bash
# Runs every submission check again on every open submission.
# Needs GH_TOKEN and GH_REPO in the environment. APPLY=true changes labels and posts comments;
# anything else is a dry run that only reports what would change.
# Verified maps that still pass stay verified; verified maps that now fail lose the label.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${APPLY:-false}" != "true" ]]; then
  export PATH="$here/dryrun:$PATH"
  echo "Dry run: nothing will be changed. Run with apply to update labels and comments."
fi

numbers=$(gh issue list --repo "$GH_REPO" --state open --limit 1000 --json number --jq '.[].number')
valid=0
invalid=0
skipped=0
summary=""

while read -r number; do
  [[ -n "$number" ]] || continue
  BODY=$(gh issue view "$number" --repo "$GH_REPO" --json body --jq .body)
  # Issues that are not map submissions have no download URL heading.
  if ! grep -q '^### Download URL' <<< "$BODY"; then
    echo "#$number: skipped (not a map submission)"
    skipped=$((skipped + 1))
    continue
  fi
  labels=$(NUMBER="$number" gh issue view "$number" --repo "$GH_REPO" --json labels --jq '[.labels[].name] | join(", ")')
  output=$(MODE=recheck NUMBER="$number" BODY="$BODY" bash "$here/on_submission.sh" 2>&1)
  result=$(grep -o 'RESULT=[a-z]*' <<< "$output" | tail -1)
  rest=$(grep -v '^RESULT=' <<< "$output")
  if [[ "$result" == "RESULT=valid" ]]; then
    echo "#$number: valid ($labels)"
    valid=$((valid + 1))
    summary+="| #$number | valid | $labels |"$'\n'
  elif [[ "$result" == "RESULT=invalid" ]]; then
    echo "#$number: INVALID ($labels)"
    invalid=$((invalid + 1))
    summary+="| #$number | **invalid** | $labels |"$'\n'
  else
    echo "#$number: no result ($labels)"
    summary+="| #$number | skipped | $labels |"$'\n'
    skipped=$((skipped + 1))
  fi
  [[ -n "$rest" ]] && sed 's/^/    /' <<< "$rest"
done <<< "$numbers"

echo
echo "$valid valid, $invalid invalid, $skipped skipped"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "## Recheck of all submissions"
    [[ "${APPLY:-false}" == "true" ]] && echo "Labels and comments were updated." || echo "Dry run: nothing was changed."
    echo
    echo "**$valid valid, $invalid invalid, $skipped skipped**"
    echo
    echo "| Issue | Result | Labels before |"
    echo "|---|---|---|"
    printf '%s' "$summary"
  } >> "$GITHUB_STEP_SUMMARY"
fi
