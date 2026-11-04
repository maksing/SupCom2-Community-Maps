#!/usr/bin/env bash
# Shared helpers for the map submission workflows.
# Needs GH_TOKEN, GH_REPO and NUMBER in the environment.

# mark_invalid "<problems, one per line>"
# Labels the issue invalid and tells the author what to fix.
mark_invalid() {
  local problems="$1"
  local message="The automatic check found problems with this submission:"$'\n\n'
  local line
  while IFS= read -r line; do
    [[ -n "$line" ]] && message+="- $line"$'\n'
  done <<< "$problems"
  message+=$'\n'"Edit the issue to fix them and it will be checked again."
  gh issue edit "$NUMBER" --repo "$GH_REPO" --add-label invalid --remove-label pending
  gh issue comment "$NUMBER" --repo "$GH_REPO" --body "$message"
}

# open_issues_mentioning "<text>"
# Prints the numbers of the other open issues whose body contains the text, as "#1, #2".
open_issues_mentioning() {
  gh issue list --repo "$GH_REPO" --state open --search "\"$1\" in:body" --json number \
    --jq "[.[].number | select(. != $NUMBER)] | map(\"#\(.)\") | join(\", \")"
}
