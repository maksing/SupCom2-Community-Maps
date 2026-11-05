#!/usr/bin/env bash
# Runs the workflow scripts against a fake gh and checks the labels, comments and SHA-256 they leave behind.
# Usage: bash .github/scripts/test_workflows.sh
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export PATH="$here/fakes:$PATH"
export GH_REPO=test/repo GH_TOKEN=x NUMBER=7 FAKE_DIR="$work/issue"

python3 - "$work" <<'PY'
import sys, zipfile
work = sys.argv[1]
with zipfile.ZipFile(work + "/good.scd", "w") as z:
    z.writestr("maps/BDFTM_Forest/BDFTM_Forest_scenario.lua", "x")
with zipfile.ZipFile(work + "/other.scd", "w") as z:
    z.writestr("maps/BDFTM_Forest/BDFTM_Forest_scenario.lua", "different file")
with zipfile.ZipFile(work + "/bad.scd", "w") as z:
    z.writestr("maps/other/other_scenario.lua", "x")
PY
good_sha=$(sha256sum "$work/good.scd" | awk '{print toupper($1)}')

failures=0
pass() { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; failures=$((failures + 1)); }

# make_body <file name> <sha or "_No response_">
make_body() {
  printf '### Map name\n\nForest\n\n### Author\n\nA\n\n### Download URL\n\nhttps://example.com/%s\n\n### Map or mappack version\n\n1.0.0\n\n### Scenario File Paths\n\n/maps/BDFTM_Forest/BDFTM_Forest_scenario.lua\n\n### Players\n\n6 Players\n\n### SHA-256 (generated automatically)\n\n%s\n\n### Publication agreement\n\n- [x] a\n- [x] b\n' "$1" "$2"
}
# start <body> <labels...>
start() {
  rm -rf "$FAKE_DIR"; mkdir -p "$FAKE_DIR"
  printf '%s\n' "$1" > "$FAKE_DIR/body.txt"; shift
  : > "$FAKE_DIR/labels.txt"; : > "$FAKE_DIR/comments.txt"
  for label in "$@"; do echo "$label" >> "$FAKE_DIR/labels.txt"; done
  unset FAKE_ARCHIVE FAKE_CONTENT_TYPE FAKE_DUPLICATES FAKE_VERIFIED FAKE_OPEN FAKE_ISSUES_FILE
}
run() { BODY=$(cat "$FAKE_DIR/body.txt") bash "$here/$1" >/dev/null; }
labels() { sort "$FAKE_DIR/labels.txt" | paste -sd, -; }
expect_labels() { [[ "$(labels)" == "$2" ]] && pass "$1" || fail "$1: labels are '$(labels)', expected '$2'"; }
expect_comment() { grep -q "$2" "$FAKE_DIR/comments.txt" && pass "$1" || fail "$1: no comment containing '$2'"; }
expect_no_comment() { [[ ! -s "$FAKE_DIR/comments.txt" ]] && pass "$1" || fail "$1: unexpected comment"; }
expect_body_has() { grep -q "$2" "$FAKE_DIR/body.txt" && pass "$1" || fail "$1: body does not contain '$2'"; }
expect_body_lacks() { grep -q "$2" "$FAKE_DIR/body.txt" && fail "$1: body contains '$2'" || pass "$1"; }

valid_name=_Map_6p_Forest_v1.0.0_by_bdftm.scd
invalid_name=Forest_1.0.scd

# --- a new submission ---
start "$(make_body $valid_name '_No response_')" pending
FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "valid new submission is pending" pending
expect_body_has "valid new submission gets its SHA-256" "$good_sha"
expect_comment "valid new submission gets a passed message" "passed the automatic check"

start "$(make_body $invalid_name '_No response_')" pending
run on_submission.sh
expect_labels "bad file name makes the submission invalid" invalid
expect_comment "bad file name is explained" "naming convention"
expect_body_lacks "invalid submission gets no SHA-256" "$good_sha"

start "$(make_body $valid_name '_No response_')" pending
FAKE_ARCHIVE=$work/bad.scd run on_submission.sh
expect_labels "scenario missing from the archive makes it invalid" invalid
expect_comment "missing scenario is explained" "not found inside"

start "$(make_body $valid_name '_No response_')" pending
run on_submission.sh
expect_labels "failed download makes it invalid" invalid

start "$(make_body $valid_name '_No response_')" pending
FAKE_ARCHIVE=$work/good.scd FAKE_CONTENT_TYPE=text/html run on_submission.sh
expect_labels "web page instead of a file makes it invalid" invalid

start "$(make_body $valid_name '_No response_')" pending
FAKE_ARCHIVE=$work/good.scd FAKE_DUPLICATES="#3" run on_submission.sh
expect_labels "duplicate submission is invalid" invalid
expect_comment "duplicate is explained" "#3"

# --- editing an existing submission ---
start "$(make_body $invalid_name '_No response_')" invalid
FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "invalid submission stays invalid without pending" invalid

start "$(make_body $valid_name '_No response_')" invalid
FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "fixed invalid submission becomes pending only" pending

start "$(make_body $valid_name "$good_sha")" verified promoted
FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "edited verified map returns to pending and keeps promoted" pending,promoted
expect_comment "edited verified map is explained" "review it again"

start "$(make_body $invalid_name "$good_sha")" verified
run on_submission.sh
expect_labels "edited verified map that became invalid is only invalid" invalid

start "$(make_body $valid_name '_No response_')" broken
FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "fixed broken map becomes pending" pending

start "$(make_body $invalid_name '_No response_')" rejected
run on_submission.sh
expect_labels "rejected submission is left alone" rejected
expect_no_comment "rejected submission gets no comment"

# --- the verified label is added ---
start "$(make_body $invalid_name '_No response_')" invalid verified
run on_verified.sh
expect_labels "verified on an invalid submission is taken back, invalid stays" invalid
expect_body_lacks "verified on an invalid submission leaves the SHA-256 alone" "$good_sha"
expect_comment "verified on an invalid submission is explained" "labeled invalid"

start "$(make_body $valid_name "$good_sha")" invalid verified
run on_verified.sh
expect_labels "verified on an invalid label is taken back even if the fields look valid" invalid

start "$(make_body $valid_name "$good_sha")" pending verified
run on_verified.sh
expect_labels "verifying a valid pending map leaves only verified" verified
expect_no_comment "verifying a valid map gets no comment"

start "$(make_body $valid_name "$good_sha")" verified promoted hidden
run on_verified.sh
expect_labels "promoted and hidden are kept" hidden,promoted,verified

start "$(make_body $valid_name '_No response_')" pending verified
run on_verified.sh
expect_labels "verified without a SHA-256 goes back to pending" pending
expect_comment "missing SHA-256 is explained" "SHA-256"

start "$(make_body $invalid_name "$good_sha")" pending verified
run on_verified.sh
expect_labels "verified on a map with invalid fields becomes invalid only" invalid

start "$(make_body $valid_name "$good_sha")" pending
run on_verified.sh
expect_labels "nothing happens when verified is already gone" pending

# --- the weekly check ---
start "$(make_body $valid_name "$good_sha")" verified
FAKE_VERIFIED=7 FAKE_ARCHIVE=$work/good.scd run check_verified.sh
expect_labels "unchanged verified map stays verified" verified

start "$(make_body $valid_name "$good_sha")" verified promoted
FAKE_VERIFIED=7 run check_verified.sh
expect_labels "verified map with a dead link becomes broken" broken,promoted

start "$(make_body $valid_name "$good_sha")" verified
FAKE_VERIFIED=7 FAKE_ARCHIVE=$work/other.scd run check_verified.sh
expect_labels "verified map whose file changed goes back to pending" pending
expect_comment "changed file is explained" "changed after this map was verified"

# --- recheck of all submissions ---
start "$(make_body $valid_name "$good_sha")" verified promoted
FAKE_OPEN=7 FAKE_ARCHIVE=$work/good.scd APPLY=true bash "$here/recheck_all.sh" >/dev/null
expect_labels "recheck keeps a valid verified map verified" promoted,verified
expect_no_comment "recheck of a valid verified map gets no comment"

start "$(make_body $invalid_name "$good_sha")" verified
FAKE_OPEN=7 APPLY=true bash "$here/recheck_all.sh" >/dev/null
expect_labels "recheck takes verified from a map that no longer passes" invalid
expect_comment "recheck explains the problem" "naming convention"

start "$(make_body $invalid_name "$good_sha")" verified
FAKE_OPEN=7 bash "$here/recheck_all.sh" > "$work/dry.txt"
expect_labels "dry run changes no labels" verified
expect_no_comment "dry run posts no comments"
grep -q "dry run\] would run" "$work/dry.txt" && pass "dry run reports what it would do" || fail "dry run does not report what it would do"
grep -q "#7: INVALID" "$work/dry.txt" && pass "dry run reports the result" || fail "dry run does not report the result"

start "$(make_body $valid_name '_No response_')" invalid
FAKE_OPEN=7 FAKE_ARCHIVE=$work/good.scd APPLY=true bash "$here/recheck_all.sh" >/dev/null
expect_labels "recheck moves a now-valid invalid map to pending" pending

start "just a question, not a submission" pending
FAKE_OPEN=7 APPLY=true bash "$here/recheck_all.sh" > "$work/skip.txt"
expect_labels "recheck leaves issues that are not submissions alone" pending
grep -q "skipped" "$work/skip.txt" && pass "recheck reports skipped issues" || fail "recheck does not report skipped issues"

# --- MD5 ---
good_md5=$(md5sum "$work/good.scd" | awk '{print toupper($1)}')

start "$(make_body $valid_name '_No response_')" pending
FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_body_has "valid submission gets its MD5" "### MD5 (generated automatically)"
expect_body_has "valid submission gets the MD5 value" "$good_md5"

start "$(make_body $valid_name "$good_sha")" verified
FAKE_OPEN=7 FAKE_ARCHIVE=$work/good.scd APPLY=true bash "$here/recheck_all.sh" >/dev/null
expect_labels "recheck of a verified map without MD5 keeps it verified" verified
expect_body_has "recheck adds the missing MD5" "$good_md5"
expect_body_has "recheck keeps the SHA-256" "$good_sha"

start "$(make_body $valid_name "$good_sha")" verified
FAKE_OPEN=7 FAKE_ARCHIVE=$work/other.scd APPLY=true bash "$here/recheck_all.sh" >/dev/null
expect_labels "recheck of a verified map whose file changed makes it invalid" invalid
expect_comment "recheck explains the changed file" "changed after the map was verified"
expect_body_has "recheck does not overwrite the verified SHA-256" "$good_sha"

# --- scenario path collisions ---
# collision_issues <number> <labels>: one other issue with the same scenario path as the issues under test
collision_issues() {
  python3 - "$(make_body $valid_name "$good_sha")" "$1" "$2" <<'PY'
import json, sys
body, number, labels = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(",")
print(json.dumps([{"number": number, "url": "", "body": body, "labels": [{"name": n} for n in labels]}]))
PY
}

start "$(make_body $valid_name '_No response_')" pending
collision_issues 3 verified > "$work/others.json"
FAKE_ISSUES_FILE=$work/others.json FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "a path used by a verified map makes the submission invalid" invalid
expect_comment "the collision names the other map" "already used by the verified map #3"

start "$(make_body $valid_name '_No response_')" pending
collision_issues 3 verified,hidden > "$work/others.json"
FAKE_ISSUES_FILE=$work/others.json FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "a hidden verified map is ignored in the collision check" pending

start "$(make_body $valid_name '_No response_')" pending hidden
collision_issues 3 verified > "$work/others.json"
FAKE_ISSUES_FILE=$work/others.json FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "a hidden submission is not checked for collisions" hidden,pending

start "$(make_body $valid_name '_No response_')" pending
collision_issues 3 pending > "$work/others.json"
FAKE_ISSUES_FILE=$work/others.json FAKE_ARCHIVE=$work/good.scd run on_submission.sh
expect_labels "a pending map with the same path is not a collision" pending

start "$(make_body $valid_name "$good_sha")" pending verified
collision_issues 3 verified > "$work/others.json"
FAKE_ISSUES_FILE=$work/others.json run on_verified.sh
expect_labels "verifying a map whose path is used by a verified map makes it invalid" invalid
expect_comment "verification explains the collision" "collisions"

start "$(make_body $valid_name "$good_sha")" pending verified
collision_issues 3 verified,hidden > "$work/others.json"
FAKE_ISSUES_FILE=$work/others.json run on_verified.sh
expect_labels "verifying is fine when the other map is hidden" verified

start "$(make_body $valid_name "$good_sha")" verified
collision_issues 3 verified > "$work/others.json"
FAKE_OPEN=7 FAKE_ISSUES_FILE=$work/others.json FAKE_ARCHIVE=$work/good.scd APPLY=true bash "$here/recheck_all.sh" >/dev/null
expect_labels "recheck makes the newer of two colliding verified maps invalid" invalid

start "$(make_body $valid_name "$good_sha")" verified
collision_issues 9 verified > "$work/others.json"
FAKE_OPEN=7 FAKE_ISSUES_FILE=$work/others.json FAKE_ARCHIVE=$work/good.scd APPLY=true bash "$here/recheck_all.sh" >/dev/null
expect_labels "recheck keeps the older of two colliding verified maps" verified

# --- the catalog branch ---
catalog_issues() { # catalog_issues <labels of issue 2>: a promoted, a community-or-other and a hidden issue
  python3 - "$(make_body $valid_name "$good_sha")" "$1" <<'PY'
import json, sys
body, labels = sys.argv[1], sys.argv[2].split(",")
def issue(number, names):
    own_body = body.replace("/maps/BDFTM_Forest/BDFTM_Forest_scenario.lua", f"/maps/F{number}/F{number}_scenario.lua")
    return {"number": number, "url": f"https://example.com/{number}", "body": own_body, "labels": [{"name": n} for n in names]}
print(json.dumps([issue(1, ["verified", "promoted"]), issue(2, labels), issue(3, ["verified", "hidden"])]))
PY
}
catalog_counts() { # prints "<official> <community>" from the catalog branch
  git -C "$work/remote.git" show catalog:maps.json | python3 -c "import json,sys; print(len(json.load(sys.stdin)), end=' ')"
  git -C "$work/remote.git" show catalog:community-maps.json | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
}
publish() { GH_BIN="bash '$here/fakes/gh'" CATALOG_REMOTE="$work/remote.git" FAKE_ISSUES_FILE="$work/issues.json" bash "$here/publish_catalog.sh" 2>&1; }
commits() { git -C "$work/remote.git" rev-list --count catalog; }

git init --quiet --bare "$work/remote.git"
catalog_issues verified > "$work/issues.json"
publish > /dev/null
[[ "$(catalog_counts)" == "1 1" ]] && pass "catalog branch is created with official and community maps" || fail "catalog counts are '$(catalog_counts)', expected '1 1'"
[[ "$(commits)" == 1 ]] && pass "first catalog build is one commit" || fail "catalog has $(commits) commits, expected 1"
git -C "$work/remote.git" show catalog:README.md | grep -q "generated automatically" && pass "catalog branch explains itself" || fail "catalog README missing"

publish | grep -q unchanged && pass "unchanged catalog is reported" || fail "unchanged catalog is not reported"
[[ "$(commits)" == 1 ]] && pass "unchanged catalog makes no new commit" || fail "catalog has $(commits) commits, expected 1"

catalog_issues verified,promoted > "$work/issues.json"
publish > /dev/null
[[ "$(catalog_counts)" == "2 0" && "$(commits)" == 2 ]] && pass "promoting a map moves it to the official file in one new commit" || fail "after promoting: '$(catalog_counts)', $(commits) commits"

catalog_issues verified,invalid > "$work/issues.json"
publish > /dev/null
[[ "$(catalog_counts)" == "1 0" ]] && pass "an invalid map disappears from the catalog" || fail "after invalid: '$(catalog_counts)'"

echo
if (( failures == 0 )); then echo "all passed"; else echo "$failures failed"; exit 1; fi
