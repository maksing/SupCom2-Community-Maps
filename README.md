# Supreme Commander 2 Community Maps

This repository contains community map submissions for Supreme Commander 2.

Submit a map through the **Publish map** issue form. A submission with `pending` has not been tested by moderators and may be unsafe or broken. Only maps with `verified` are presented as verified in SC2 Mod Manager.

Supported downloads are direct HTTPS links to `.scd` or `.zip` files. The map name, author, download URL, map or mappack version, one or more Scenario File Paths, and publication agreement are required. The version must contain exactly three numeric components, such as `1.17.2`. Enter one Scenario File Path per line; every path must end with `.lua`, for example `/maps/bdftm_tranquility/bdftm_tranquility_scenario.lua`. Description, player count, style, size, tags, and the map preview image are optional and follow the same metadata used by the official catalog. The image is added while filling out the form by dragging it into the **Map image** field or pasting it there; GitHub stores it as an attachment URL.

If the automatic check finds a problem, it labels the issue `invalid` and comments with what to fix; editing the issue runs the check again. The file type is taken from the download URL, which must end with `.scd` or `.zip`.

Moderators may mark submissions `verified`, `rejected`, `broken`, or `invalid`. Editing a verified submission returns it to `pending` for another review. Missing optional metadata is shown as `Unknown` or `No description available.` in the launcher.
