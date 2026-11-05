#!/usr/bin/env bash
# Shared helpers for the map submission workflows.
# Needs GH_TOKEN, GH_REPO and NUMBER in the environment.
#
# An issue has exactly one status label at a time: pending, verified, invalid or broken.
# rejected is a moderator decision that the automation never changes. promoted and hidden are
# modifiers of verified maps and are never touched here.

STATUS_LABELS=(pending verified invalid broken)

validate_script="$(dirname "${BASH_SOURCE[0]}")/validate_submission.py"

# current_labels: prints the labels of the issue, one per line.
current_labels() {
  gh issue view "$NUMBER" --repo "$GH_REPO" --json labels --jq '.labels[].name'
}

# has_label <name> [labels]: succeeds when the label is on the issue.
has_label() {
  local labels="${2:-$(current_labels)}"
  grep -qxF "$1" <<< "$labels"
}

# set_status <status>: gives the issue the status label and removes the other status labels.
set_status() {
  local target="$1" args=() status
  local labels
  labels=$(current_labels)
  for status in "${STATUS_LABELS[@]}"; do
    if [[ "$status" == "$target" ]]; then
      has_label "$status" "$labels" || args+=(--add-label "$status")
    else
      has_label "$status" "$labels" && args+=(--remove-label "$status")
    fi
  done
  if (( ${#args[@]} > 0 )); then
    gh issue edit "$NUMBER" --repo "$GH_REPO" "${args[@]}"
  fi
}

# bullet_list "<lines>": turns lines into a markdown bullet list.
bullet_list() {
  local line out=""
  while IFS= read -r line; do
    [[ -n "$line" ]] && out+="- $line"$'\n'
  done <<< "$1"
  printf '%s' "$out"
}

# mark_invalid "<problems, one per line>": invalid status and a comment that tells the author what to fix.
mark_invalid() {
  echo "RESULT=invalid"
  set_status invalid
  gh issue comment "$NUMBER" --repo "$GH_REPO" --body "The automatic check found problems with this submission:"$'\n\n'"$(bullet_list "$1")"$'\n'"Edit the issue to fix them and it will be checked again."
}

# open_issues_mentioning "<text>": prints the numbers of the older open issues whose body contains the text, as "#1, #2".
# Only older issues count, so of two duplicates the first one keeps its status.
open_issues_mentioning() {
  gh issue list --repo "$GH_REPO" --state open --search "\"$1\" in:body" --json number \
    --jq "[.[].number | select(. < $NUMBER)] | map(\"#\(.)\") | join(\", \")"
}

# scenario_collisions [--newer-only]: prints the scenario paths of the issue (BODY) that another verified map
# already uses. Hidden maps are neither checked nor counted. With --newer-only only older issues count.
scenario_collisions() {
  local issues_file args=()
  issues_file=$(mktemp)
  gh issue list --repo "$GH_REPO" --state open --label verified --limit 1000 --json number,body,labels,url > "$issues_file"
  [[ "${1:-}" == "--newer-only" ]] && args+=(--newer-only)
  has_label hidden && args+=(--hidden)
  python3 "$validate_script" collisions "$issues_file" "$NUMBER" ${args[@]+"${args[@]}"}
  rm -f "$issues_file"
}

# without_blank_lines "<text>"
without_blank_lines() {
  sed '/^[[:space:]]*$/d' <<< "$1"
}
