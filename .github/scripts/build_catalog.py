#!/usr/bin/env python3
"""Builds the map catalog JSON files from the verified issues.

Usage: build_catalog.py ISSUES.json OUTPUT_DIR
       build_catalog.py --fetch OUTPUT_DIR     read the issues with gh (needs GH_REPO and GH_TOKEN; GH_BIN overrides the gh command, for tests)

ISSUES.json is a list of {"number", "url", "body", "labels": [{"name"}], "verifiedAt"} objects, one per open
issue that has the verified label. The output directory gets:
    maps.json             official maps: verified and promoted
    community-maps.json   community maps: verified, not promoted
Issues with the hidden label are left out of both, and so are issues that carry another status label
(pending, invalid, broken), have no SHA-256 yet, or do not pass the field checks.
The files have the same structure as the old maps.json of the SC2Mods repository and contain nothing that
changes between runs, so an unchanged catalog produces identical files.
"""
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

import validate_submission as v

SHA_HEADING = v.SHA_HEADING
MD5_HEADING = v.MD5_HEADING


def image_url(text):
    """The first https image link of a 'Map image' value: markdown, <img src> or a bare link."""
    if not text:
        return ""
    markdown = re.search(r"!\[[^\]]*\]\((https://[^)\s]+)", text, re.IGNORECASE)
    html = re.search(r"""<img\b[^>]*?\bsrc\s*=\s*["'](https://[^"']+)["']""", text, re.IGNORECASE)
    bare = re.search(r"""https://[^\s)"'<>]+""", text, re.IGNORECASE)
    for match in (markdown, html, bare):
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return ""


def date_only(timestamp):
    """dd.MM.yyyy of an ISO timestamp, like the dates of the old maps.json."""
    if not timestamp:
        return ""
    try:
        return datetime.strptime(timestamp[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return ""


def known(text):
    return "" if text in ("", "Unknown", "_No response_") else text


def players(text):
    match = re.match(r"^(\d+)\s+Players?$", text or "")
    return match.group(1) if match else ""


def entry(issue, official):
    body = issue.get("body") or ""
    url = v.value(body, "Download URL").replace(" ", "")
    file_name = posixpath.basename(urlparse(url).path)
    paths = v.scenario_paths(body)
    tags = [tag.strip() for tag in v.value(body, "Tags").split(",") if tag.strip()]
    return {
        "id": file_name,
        "fileName": file_name,
        "author": v.value(body, "Author"),
        "type": "Map",
        "version": "v" + v.value(body, "Map or mappack version"),
        "lastUpdatedDate": date_only(issue.get("verifiedAt")),
        "downloadURL": url,
        "playerCount": players(v.value(body, "Players")),
        "mapTeamStyle": known(v.value(body, "Style")),
        "size": known(v.value(body, "Size")),
        "mapName": v.value(body, "Map name"),
        "description": v.value(body, "Description").replace("_No response_", ""),
        "mapPictureFileName": "",
        "mapPictureUrl": image_url(v.value(body, "Map image")),
        "tags": tags,
        "scenarioFilePath": "\n".join(paths),
        "catalogSource": "official" if official else "community",
        "sourceIssueNumber": issue["number"],
        "sourceIssueUrl": issue.get("url", ""),
        "moderationStatus": "verified",
        "sha256": v.value(body, SHA_HEADING).replace(" ", "").upper(),
        "modHash": v.value(body, MD5_HEADING).replace(" ", "").upper(),
    }


def build(issues):
    official, community = [], []
    used = set()
    for issue in sorted(issues, key=lambda i: i["number"]):
        labels = {label["name"].lower() for label in issue.get("labels", [])}
        if "verified" not in labels or "hidden" in labels or labels & {"pending", "invalid", "broken", "rejected"}:
            continue
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", v.value(issue.get("body") or "", SHA_HEADING).replace(" ", "")):
            print(f"#{issue['number']}: skipped, no SHA-256 yet", file=sys.stderr)
            continue
        if not v.scenario_paths(issue.get("body") or ""):
            print(f"#{issue['number']}: skipped, no scenario paths yet", file=sys.stderr)
            continue
        problems = v.check_fields(issue.get("body") or "")
        if problems:
            print(f"#{issue['number']}: skipped, {problems[0]}", file=sys.stderr)
            continue
        # No two maps of the catalog may share a scenario path; the older map keeps it.
        keys = {v.path_key(path) for path in v.scenario_paths(issue.get("body") or "")}
        taken = keys & used
        if taken:
            print(f"#{issue['number']}: skipped, scenario path {sorted(taken)[0]} is used by an older map", file=sys.stderr)
            continue
        used |= keys
        is_official = "promoted" in labels
        (official if is_official else community).append(entry(issue, is_official))
    return official, community


def write(path, maps):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(maps, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def gh(*args):
    return subprocess.run([*shlex.split(os.environ.get("GH_BIN", "gh")), *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def fetch_issues():
    """The open verified issues, each with the time its verified label was last added."""
    repo = os.environ["GH_REPO"]
    issues = json.loads(gh("issue", "list", "--repo", repo, "--state", "open", "--label", "verified",
                           "--limit", "1000", "--json", "number,body,labels,url"))
    for issue in issues:
        lines = gh("api", f"repos/{repo}/issues/{issue['number']}/events", "--paginate", "--jq",
                   '.[] | select(.event == "labeled" and .label.name == "verified") | .created_at').split()
        issue["verifiedAt"] = lines[-1] if lines else ""
    return issues


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    if sys.argv[1] == "--fetch":
        issues = fetch_issues()
    else:
        with open(sys.argv[1], encoding="utf-8") as handle:
            issues = json.load(handle)
    official, community = build(issues)
    os.makedirs(sys.argv[2], exist_ok=True)
    write(os.path.join(sys.argv[2], "maps.json"), official)
    write(os.path.join(sys.argv[2], "community-maps.json"), community)
    print(f"{len(official)} official, {len(community)} community")


if __name__ == "__main__":
    main()
