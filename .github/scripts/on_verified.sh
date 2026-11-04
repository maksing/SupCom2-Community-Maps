#!/usr/bin/env bash
# Runs when the verified label is added to an issue. A submission can only be verified when it is valid;
# otherwise the label is taken back and the issue keeps (or gets) the status that explains why.
# Needs BODY, NUMBER, GH_TOKEN and GH_REPO in the environment.
set -uo pipefail
here="$(dirname "${BASH_SOURCE[0]}")"
source "$here/common.sh"

labels=$(current_labels)
# The label may have been removed again before this ran.
has_label verified "$labels" || exit 0

if has_label invalid "$labels"; then
  set_status invalid
  gh issue comment "$NUMBER" --repo "$GH_REPO" --body "The verified label was removed because this submission is labeled invalid. Fix the problems from the automatic check (edit the issue) and verify it again once it is back in the pending queue."
  exit 0
fi

errors=$(python3 "$validate_script" fields)
if [[ -n "$errors" ]]; then
  set_status invalid
  gh issue comment "$NUMBER" --repo "$GH_REPO" --body "The verified label was removed because the submission has problems:"$'\n\n'"$(bullet_list "$errors")"$'\n'"Edit the issue to fix them and it will be checked again."
  exit 0
fi

sha=$(python3 "$validate_script" sha)
if ! [[ "$sha" =~ ^[0-9A-Fa-f]{64}$ ]]; then
  set_status pending
  gh issue comment "$NUMBER" --repo "$GH_REPO" --body "The verified label was removed because the SHA-256 was not generated yet. Wait for the automatic check to finish (or edit the issue to run it again) and verify it again."
  exit 0
fi

set_status verified
