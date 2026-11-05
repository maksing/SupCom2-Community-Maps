# Supreme Commander 2 Community Maps

This repository contains community map submissions for Supreme Commander 2.

Submit a map through the **Publish map** issue form. A submission with `pending` has not been tested by moderators and may be unsafe or broken. Only maps with `verified` are presented as verified in SC2 Mod Manager.

Every submission must follow the [community map rules](RULES.md); the form asks you to confirm this.

Supported downloads are direct HTTPS links to `.scd` or `.zip` files. The map name, author, download URL, map or mappack version, and publication agreement are required. The version must contain exactly three numeric components, such as `1.17.2`. Leave **Scenario File Paths** empty: the automatic check reads the `*_scenario.lua` files from the root `maps` folder of your file (not from `uncompiled`) and fills the field in, one path per line, for example `/maps/bdftm_tranquility/bdftm_tranquility_scenario.lua`. The same check fills in the SHA-256 and MD5. Description, player count, style, size, tags, and the map preview image are optional and follow the same metadata used by the official catalog. The image is added while filling out the form by dragging it into the **Map image** field or pasting it there; GitHub stores it as an attachment URL.

If the automatic check finds a problem, it labels the issue `invalid` and comments with what to fix; editing the issue runs the check again. The file type is taken from the download URL, which must end with `.scd` or `.zip`.

Moderators may mark submissions `verified`, `rejected`, `broken`, or `invalid`. Editing a verified submission returns it to `pending` for another review. Missing optional metadata is shown as `Unknown` or `No description available.` in the launcher.

## Automatic checks

Every submission is checked when it is opened or edited. If a check fails, the issue is labeled `invalid` and a comment lists everything to fix:

- **File name** (the last part of the download URL) must follow the naming convention: `_Map_8p_MapName_v1.0.0_by_author.scd` for maps, `_CustomMission_1p_MissionName_v1.0.0_by_author.scd` for custom missions, and `_MapPack_PackName_v1.0.0_by_author.scd` for map packs (no player count). The name uses letters, digits and `-` only, `_by_author` is optional (the author, like the name, uses letters, digits and `-`), and the player count is `1p` to `8p`.
- The version in the file name must equal **Map or mappack version**, and **Players** must match the player count in the file name.
- The downloaded file must have at least one `*_scenario.lua` in its root `maps` folder; those paths become **Scenario File Paths** (they may only use letters, digits, `_`, `-`, `.` and `/`).
- **Scenario File Paths**, **SHA-256** and **MD5** are filled in by the check. A map cannot be verified until all three are there: adding `verified` without them is undone and the map goes back to `pending`.
- The download must be a direct link to a valid archive of at most 512 MB, not a web page, and must not contain executables or scripts.
- The same download URL or file (SHA-256) must not already be submitted in another open issue.
- Every single **Scenario File Path** must be unique among verified maps: if another verified map already uses one of the paths (whatever else the two maps contain), the submission becomes `invalid`, and so does a map that is verified while it collides. Maps that are also labeled `hidden` are not part of the catalog and are left out of this check. When everything is rechecked, the older of two colliding maps keeps its status.

When a submission passes all checks, the bot comments that it passed and shows the SHA-256 and MD5 of the file.
- The name, author and description must not be too long, and every box of the publication agreement must be ticked.

An issue always has exactly one status label: `pending`, `verified`, `invalid` or `broken` (`rejected` is a moderator decision that the automation never changes, and `promoted` and `hidden` are kept as they are). Adding `verified` to an `invalid` or incomplete submission is undone with a comment, and editing a verified map returns it to `pending`.

Verified maps are downloaded again every week. A map whose download stops working is labeled `broken`, and a map whose file changed after it was verified goes back to `pending`; in both cases the `verified` label is removed.

## Rechecking all submissions

After the rules or checks change, run **Actions → Recheck all submissions → Run workflow**. It runs every check again on every open map submission and lists the result per issue in the run summary. By default it is a dry run that changes nothing; tick **apply** to update labels and post comments. Verified maps that still pass stay verified, verified maps that now fail lose the label and become `invalid`, and `rejected` submissions are skipped.

## Catalog for the launcher

The launcher does not read the issues; it reads two JSON files that the **Update catalog** workflow keeps on the `catalog` branch:

- `maps.json`: official maps, issues labeled `verified` and `promoted`
- `community-maps.json`: community maps, issues labeled `verified` without `promoted`

Maps labeled `hidden` are in neither file, and neither are maps that also have `pending`, `invalid`, `broken` or `rejected`. The files have the structure of the old `maps.json` and are rebuilt when labels or issues change, after the validation workflows finish, and every night; a commit is only made when the content changed. Each entry also has the generated `sha256` and `modHash` (MD5), which the workflow fills into the issue when the file is checked. Do not edit the branch by hand. It is served at `https://raw.githubusercontent.com/maksing/SupCom2-Community-Maps/catalog/maps.json` (and `community-maps.json`).
