import unittest

import build_catalog as b
from test_validate_submission import body

SHA = "A" * 64
MD5 = "B" * 32


def issue(number, labels, **fields):
    defaults = {
        "Scenario File Paths": f"/maps/Map{number}/Map{number}_scenario.lua",
        "SHA-256 (generated automatically)": SHA,
        "MD5 (generated automatically)": MD5,
        "Style": "3v3",
        "Size": "Medium",
        "Tags": "6 Players, Team, Medium",
        "Map image": '<img width="1024" alt="Image" src="https://github.com/user-attachments/assets/abc" />',
    }
    defaults.update(fields)
    return {
        "number": number,
        "url": f"https://github.com/maksing/SupCom2-Community-Maps/issues/{number}",
        "body": body(**defaults),
        "labels": [{"name": name} for name in labels],
        "verifiedAt": "2026-11-04T16:44:09Z",
    }


class CatalogTests(unittest.TestCase):
    def test_official_community_and_hidden(self):
        issues = [
            issue(3, ["verified"]),
            issue(1, ["verified", "promoted"]),
            issue(2, ["verified", "promoted", "hidden"]),
            issue(4, ["verified", "hidden"]),
            issue(5, ["pending"]),
        ]
        official, community = b.build(issues)
        self.assertEqual([m["sourceIssueNumber"] for m in official], [1])
        self.assertEqual([m["sourceIssueNumber"] for m in community], [3])
        self.assertEqual(official[0]["catalogSource"], "official")
        self.assertEqual(community[0]["catalogSource"], "community")

    def test_entry_has_the_structure_of_the_old_maps_json(self):
        official, _ = b.build([issue(1, ["verified", "promoted"])])
        m = official[0]
        self.assertEqual(m["fileName"], "_Map_6p_Forest_v1.0.0_by_bdftm.scd")
        self.assertEqual(m["id"], m["fileName"])
        self.assertEqual(m["author"], "foxtermelon")
        self.assertEqual(m["type"], "Map")
        self.assertEqual(m["version"], "v1.0.0")
        self.assertEqual(m["lastUpdatedDate"], "04.11.2026")
        self.assertEqual(m["downloadURL"], "https://github.com/user/repo/releases/download/Forest_v1.0.0/_Map_6p_Forest_v1.0.0_by_bdftm.scd")
        self.assertEqual(m["playerCount"], "6")
        self.assertEqual(m["mapTeamStyle"], "3v3")
        self.assertEqual(m["size"], "Medium")
        self.assertEqual(m["mapName"], "Forest")
        self.assertEqual(m["description"], "Test")
        self.assertEqual(m["tags"], ["6 Players", "Team", "Medium"])
        self.assertEqual(m["scenarioFilePath"], "/maps/Map1/Map1_scenario.lua")
        self.assertEqual(m["mapPictureUrl"], "https://github.com/user-attachments/assets/abc")
        self.assertEqual(m["sha256"], SHA)
        self.assertEqual(m["modHash"], MD5)
        self.assertEqual(m["sourceIssueNumber"], 1)

    def test_unknown_values_become_empty(self):
        official, _ = b.build([issue(1, ["verified", "promoted"], Players="Unknown", Style="_No response_", Size="Unknown",
                                     Tags="_No response_", Description="_No response_")])
        m = official[0]
        self.assertEqual((m["playerCount"], m["mapTeamStyle"], m["size"], m["description"], m["tags"]), ("", "", "", "", []))

    def test_multiple_scenario_paths_are_one_per_line(self):
        _, community = b.build([issue(1, ["verified"], **{"Scenario File Paths": "/maps/a/a.lua;/maps/a/b.lua"})])
        self.assertEqual(community[0]["scenarioFilePath"], "/maps/a/a.lua\n/maps/a/b.lua")

    def test_other_status_labels_and_missing_sha_are_left_out(self):
        issues = [
            issue(1, ["verified", "invalid"]),
            issue(2, ["verified", "pending"]),
            issue(3, ["verified", "broken"]),
            issue(4, ["verified"], **{"SHA-256 (generated automatically)": "_No response_"}),
            issue(5, ["verified"]),
        ]
        _, community = b.build(issues)
        self.assertEqual([m["sourceIssueNumber"] for m in community], [5])

    def test_a_shared_scenario_path_keeps_only_the_older_map(self):
        issues = [
            issue(5, ["verified"], **{"Scenario File Paths": "/maps/A/A_scenario.lua\n/maps/B/B_scenario.lua"}),
            issue(3, ["verified", "promoted"], **{"Scenario File Paths": "/maps/b/b_SCENARIO.lua"}),
            issue(7, ["verified"], **{"Scenario File Paths": "/maps/C/C_scenario.lua"}),
        ]
        official, community = b.build(issues)
        self.assertEqual([m["sourceIssueNumber"] for m in official], [3])
        self.assertEqual([m["sourceIssueNumber"] for m in community], [7])

    def test_a_hidden_map_does_not_take_a_scenario_path(self):
        issues = [issue(3, ["verified", "hidden"]), issue(5, ["verified"])]
        _, community = b.build(issues)
        self.assertEqual([m["sourceIssueNumber"] for m in community], [5])

    def test_invalid_issue_is_left_out(self):
        official, community = b.build([issue(1, ["verified"], **{"Download URL": "https://example.com/bad.scd"})])
        self.assertEqual((official, community), ([], []))

    def test_output_does_not_depend_on_the_input_order(self):
        issues = [issue(2, ["verified"]), issue(1, ["verified"])]
        self.assertEqual(b.build(issues), b.build(list(reversed(issues))))

    def test_image_urls(self):
        self.assertEqual(b.image_url("![x](https://a.b/c.png)"), "https://a.b/c.png")
        self.assertEqual(b.image_url('<img src="https://a.b/c.png" />'), "https://a.b/c.png")
        self.assertEqual(b.image_url("see https://a.b/c.png now"), "https://a.b/c.png")
        self.assertEqual(b.image_url("http://a.b/c.png"), "")
        self.assertEqual(b.image_url(""), "")


if __name__ == "__main__":
    unittest.main()
