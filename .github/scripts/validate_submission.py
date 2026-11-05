#!/usr/bin/env python3
"""Automatic checks for community map submissions.

Usage (the issue body is read from the BODY environment variable):
    validate_submission.py fields          print the problems found in the form fields, one per line
    validate_submission.py archive FILE    print the problems found in the downloaded file, one per line
    validate_submission.py collisions ISSUES.json NUMBER [--newer-only] [--hidden]
                                           print the scenario paths that another verified map already uses
    validate_submission.py scenarios FILE  print the scenario files of the downloaded archive (root maps folder)
    validate_submission.py set-scenarios PATHS_FILE
                                           print the issue body with the scenario paths from the file filled in
    validate_submission.py paths           print the scenario paths currently in the issue body
    validate_submission.py url             print the download URL
    validate_submission.py sha             print the generated SHA-256, if any
    validate_submission.py md5             print the generated MD5, if any
    validate_submission.py hashes SHA MD5 [--keep-sha]
                                           print the issue body with the generated SHA-256 and MD5 filled in;
                                           --keep-sha leaves an existing SHA-256 untouched

The commands that check things exit with 0 and an empty output when everything is fine.
Output lines are meant to be posted as an issue comment, so they are written for the map author.
"""
import json
import os
import posixpath
import re
import sys
import zipfile
from urllib.parse import urlparse

# _Map_8p_Name_v1.0.0_by_author.scd, _MapPack_Name_v1.0.0_by_author.scd, _CustomMission_1p_Name_v1.0.0_by_author.scd
FILE_NAME = re.compile(
    r"^_(?P<kind>Map|MapPack|CustomMission)_(?:(?P<players>\d)p_)?(?P<name>[A-Za-z0-9-]+)"
    r"_v(?P<version>\d+\.\d+\.\d+)(?:_by_(?P<by>[A-Za-z0-9-]+))?\.(?P<ext>scd|zip)$"
)
EXPECTED_NAME = "`_Map_8p_MapName_v1.0.0_by_author.scd` (maps and custom missions), `_MapPack_PackName_v1.0.0_by_author.scd` (map packs)"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
SCENARIO_PATH = re.compile(r"^/maps/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.lua$", re.IGNORECASE)
FORBIDDEN_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".com", ".msi", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf",
    ".sh", ".scr", ".jar", ".lnk", ".reg", ".py", ".so", ".dylib",
}
NESTED_ARCHIVES = (".scd", ".zip")
MAX_NAME = 80
MAX_AUTHOR = 120
MAX_DESCRIPTION = 2000
MAX_SCENARIOS = 100
MAX_ENTRIES = 20000
MAX_UNCOMPRESSED = 2 * 1024 * 1024 * 1024


def section(body, name):
    """Lines of a '### name' section of the issue body, without blank lines or carriage returns."""
    lines, found = [], False
    for line in body.splitlines():
        line = line.rstrip("\r")
        if line == f"### {name}":
            found = True
            continue
        if line.startswith("### "):
            found = False
        if found and line.strip():
            lines.append(line.strip())
    return lines


def value(body, name):
    lines = section(body, name)
    text = " ".join(lines).strip()
    return "" if text == "_No response_" else text


def scenario_paths(body):
    raw = "\n".join(section(body, "Scenario File Paths"))
    parts = re.split(r"[;\n]", raw)
    return [p.strip() for p in parts if p.strip() and p.strip() != "_No response_"]


def check_fields(body):
    errors = []

    name, author = value(body, "Map name"), value(body, "Author")
    url, version = value(body, "Download URL"), value(body, "Map or mappack version")

    for label, text in (("Map name", name), ("Author", author), ("Download URL", url),
                        ("Map or mappack version", version)):
        if not text:
            errors.append(f"**{label}** is required.")

    if name and (len(name) > MAX_NAME or re.search(r"[<>]", name)):
        errors.append(f"**Map name** must be at most {MAX_NAME} characters and must not contain `<` or `>`.")
    if author and (len(author) > MAX_AUTHOR or re.search(r"[<>]", author)):
        errors.append(f"**Author** must be at most {MAX_AUTHOR} characters and must not contain `<` or `>`.")
    if len(value(body, "Description")) > MAX_DESCRIPTION:
        errors.append(f"**Description** must be at most {MAX_DESCRIPTION} characters.")

    if version and not VERSION.match(version):
        errors.append("**Map or mappack version** must be exactly three numbers such as `1.0.0`.")

    file_name = None
    if url:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append("**Download URL** must be a direct HTTPS link.")
        elif not parsed.path.lower().endswith((".scd", ".zip")) or parsed.query or parsed.fragment:
            errors.append("**Download URL** must end with `.scd` or `.zip`, without a query string.")
        else:
            file_name = posixpath.basename(parsed.path)

    if file_name:
        match = FILE_NAME.match(file_name)
        if not match:
            errors.append(
                f"The file name `{file_name}` does not follow the naming convention. Use {EXPECTED_NAME}: "
                "letters, digits and `-` in the name, no spaces, and the version as `_vX.Y.Z`. "
                "Rename the file, upload it again, and update the **Download URL**."
            )
        else:
            kind, players = match.group("kind"), match.group("players")
            if kind in ("Map", "CustomMission") and not players:
                errors.append(f"The file name `{file_name}` must contain the player count, for example `_{kind}_8p_...`.")
            if kind == "MapPack" and players:
                errors.append(f"The file name `{file_name}` is a map pack, so it must not contain a player count such as `{players}p`.")
            if players and not 1 <= int(players) <= 8:
                errors.append(f"The player count in the file name must be between `1p` and `8p`, not `{players}p`.")
            if version and VERSION.match(version) and match.group("version") != version:
                errors.append(
                    f"The version in the file name (`v{match.group('version')}`) does not match "
                    f"**Map or mappack version** (`{version}`)."
                )
            selected = value(body, "Players")
            if players and selected and selected != "Unknown":
                expected = "1 Player" if players == "1" else f"{players} Players"
                if selected != expected:
                    errors.append(f"**Players** is `{selected}` but the file name says `{players}p`. They must match.")

    agreement = section(body, "Publication agreement")
    if agreement and not all(line.startswith("- [x]") or line.startswith("- [X]") for line in agreement):
        errors.append("Every box in **Publication agreement** must be ticked, including the community map rules.")

    return errors


def archive_members(path):
    """Names of all entries of a zip archive, including the entries of archives nested one level deep."""
    members = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        members.extend((info.filename, None) for info in infos)
        for info in infos:
            if info.filename.lower().endswith(NESTED_ARCHIVES) and not info.is_dir() and info.file_size < 512 * 1024 * 1024:
                try:
                    with archive.open(info) as handle:
                        with zipfile.ZipFile(handle) as nested:
                            members.extend((n.filename, info.filename) for n in nested.infolist())
                except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError):
                    pass
    return members


def check_archive(body, path):
    errors = []
    try:
        members = archive_members(path)
    except zipfile.BadZipFile:
        return ["The downloaded file is not a valid `.scd`/`.zip` archive. Check that the link points to the map file itself."]
    except (NotImplementedError, RuntimeError):
        return ["The downloaded archive could not be read. Encrypted or unusual archives are not supported."]

    if not members:
        return ["The downloaded archive is empty."]
    if len(members) > MAX_ENTRIES:
        errors.append(f"The archive contains more than {MAX_ENTRIES} files.")

    with zipfile.ZipFile(path) as archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED:
            errors.append("The archive is larger than 2 GB when unpacked.")

    names = [name for name, _ in members]
    unsafe = [n for n in names if n.startswith("/") or ".." in n.replace("\\", "/").split("/") or re.match(r"^[A-Za-z]:", n)]
    if unsafe:
        errors.append(f"The archive contains unsafe paths, for example `{unsafe[0][:80]}`.")

    forbidden = sorted({n for n in names if os.path.splitext(n.lower())[1] in FORBIDDEN_EXTENSIONS})
    if forbidden:
        errors.append(
            "The archive contains files that are not allowed in a map (executables or scripts), for example "
            f"`{forbidden[0][:80]}`."
        )

    found = find_scenarios(path)
    if not found:
        errors.append(
            "The archive has no scenario file: a `*_scenario.lua` file in the root `maps` folder "
            "(for example `maps/MapName/MapName_scenario.lua`) is required. Files in `uncompiled/maps` do not count."
        )
    if len(found) > MAX_SCENARIOS:
        errors.append(f"The archive has more than {MAX_SCENARIOS} scenario files.")
    for scenario in found[:MAX_SCENARIOS]:
        if not SCENARIO_PATH.match(scenario) or ".." in scenario.split("/"):
            errors.append(
                f"The scenario file `{scenario[:80]}` may only use letters, digits, `_`, `-`, `.` and `/` in its path."
            )

    return errors


def is_scenario(name):
    lowered = name.replace("\\", "/").lstrip("/").lower()
    return lowered.startswith("maps/") and lowered.endswith("_scenario.lua")


def find_scenarios(path):
    """The scenario files of an archive as /maps/... paths, sorted.

    They are the *_scenario.lua files in the root maps folder; uncompiled/maps does not count. An archive
    without a root maps folder (a .zip that holds .scd files) uses the root maps folders of its nested archives.
    """
    try:
        members = archive_members(path)
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError):
        return []
    outer = {"/" + name.replace("\\", "/").lstrip("/") for name, container in members if container is None and is_scenario(name)}
    nested = {"/" + name.replace("\\", "/").lstrip("/") for name, container in members if container is not None and is_scenario(name)}
    return sorted(outer or nested, key=str.lower)


def with_scenarios(body, paths):
    """Body with the scenario file paths filled in, one per line."""
    return set_section(body, "Scenario File Paths", "\n".join(paths))


def path_key(path):
    """Scenario paths are compared without case and without the leading slash."""
    return path.strip().lower().lstrip("/")


def check_collisions(body, number, issues, newer_only=False, hidden=False):
    """Problems for scenario paths that another verified map already uses.

    Only single paths count: one shared path is a collision, whatever else the two maps contain.
    Hidden maps are not in the catalog, so they neither collide nor are checked (hidden says whether this
    issue is hidden). With newer_only, only lower-numbered issues count, so of two colliding maps the older
    one keeps its status.
    """
    if hidden:
        return []
    owners = {}
    for other in issues:
        names = {label["name"].lower() for label in other.get("labels", [])}
        if other["number"] == number or "verified" not in names or "hidden" in names:
            continue
        if newer_only and other["number"] > number:
            continue
        for path in scenario_paths(other.get("body") or ""):
            owners.setdefault(path_key(path), []).append(other)

    errors, reported = [], set()
    for path in scenario_paths(body):
        key = path_key(path)
        if key in reported or key not in owners:
            continue
        reported.add(key)
        users = ", ".join(f"#{o['number']}" for o in owners[key])
        errors.append(
            f"The scenario file path `{path[:80]}` is already used by the verified map {users}. "
            "Every map needs its own scenario paths: rename the map folder and files inside the archive, "
            "upload it again, and update **Scenario File Paths** and the **Download URL**."
        )
    return errors


SHA_HEADING = "SHA-256 (generated automatically)"
MD5_HEADING = "MD5 (generated automatically)"


def set_section(body, heading, text, after=None):
    """Body with the value of a '### heading' section replaced, or the section added when it is missing.

    A missing section goes right after the `after` section, or at the end of the body.
    """
    newline = "\r\n" if "\r\n" in body else "\n"
    lines = body.replace("\r\n", "\n").split("\n")

    def bounds(name):
        for start, line in enumerate(lines):
            if line == f"### {name}":
                end = start + 1
                while end < len(lines) and not lines[end].startswith("### "):
                    end += 1
                return start, end
        return None

    found = bounds(heading)
    if found:
        start, end = found
        lines[start + 1:end] = ["", text, ""] if end < len(lines) else ["", text]
    else:
        anchor = bounds(after) if after else None
        position = anchor[1] if anchor else len(lines)
        if position < len(lines):
            lines[position:position] = [f"### {heading}", "", text, ""]
        else:
            while lines and lines[-1] == "":
                lines.pop()
            lines.extend(["", f"### {heading}", "", text])
    return newline.join(lines)


def with_hashes(body, sha256, md5, keep_sha=False):
    """Body with the generated SHA-256 and MD5 filled in."""
    if not (keep_sha and value(body, SHA_HEADING)):
        body = set_section(body, SHA_HEADING, sha256)
    return set_section(body, MD5_HEADING, md5, after=SHA_HEADING)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    body = os.environ.get("BODY", "")
    if command == "hashes" and len(sys.argv) > 3:
        sys.stdout.write(with_hashes(body, sys.argv[2], sys.argv[3], "--keep-sha" in sys.argv[4:]))
        return
    if command == "scenarios" and len(sys.argv) > 2:
        for scenario in find_scenarios(sys.argv[2]):
            print(scenario)
        return
    if command == "set-scenarios" and len(sys.argv) > 2:
        with open(sys.argv[2], encoding="utf-8") as handle:
            sys.stdout.write(with_scenarios(body, [line.strip() for line in handle if line.strip()]))
        return
    if command == "paths":
        for scenario in scenario_paths(body):
            print(scenario)
        return
    if command == "md5":
        print(value(body, MD5_HEADING).replace(" ", ""))
        return
    if command == "fields":
        errors = check_fields(body)
    elif command == "archive" and len(sys.argv) > 2:
        errors = check_archive(body, sys.argv[2])
    elif command == "collisions" and len(sys.argv) > 3:
        with open(sys.argv[2], encoding="utf-8") as handle:
            issues = json.load(handle)
        errors = check_collisions(body, int(sys.argv[3]), issues, newer_only="--newer-only" in sys.argv[4:],
                                  hidden="--hidden" in sys.argv[4:])
    elif command == "url":
        print(value(body, "Download URL").replace(" ", ""))
        return
    elif command == "sha":
        print(value(body, "SHA-256 (generated automatically)").replace(" ", ""))
        return
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    for error in errors:
        print(error)


if __name__ == "__main__":
    main()
