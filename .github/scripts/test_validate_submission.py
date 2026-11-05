import os
import tempfile
import unittest
import zipfile

import validate_submission as v


def body(**overrides):
    fields = {
        "Map name": "Forest",
        "Author": "foxtermelon",
        "Download URL": "https://github.com/user/repo/releases/download/Forest_v1.0.0/_Map_6p_Forest_v1.0.0_by_bdftm.scd",
        "Map or mappack version": "1.0.0",
        "Scenario File Paths": "/maps/BDFTM_Forest/BDFTM_Forest_scenario.lua",
        "Description": "Test",
        "Players": "6 Players",
        "Publication agreement": "- [x] I have the right.\n- [x] I agree to the rules.",
    }
    fields.update(overrides)
    return "\n\n".join(f"### {k}\n\n{val}" for k, val in fields.items())


class FieldTests(unittest.TestCase):
    def test_valid_submission(self):
        self.assertEqual(v.check_fields(body()), [])

    def test_existing_official_file_names_match_the_convention(self):
        names = [
            "_Map_8p_Greenland_v1.0.0_by_bdftm.scd",
            "_MapPack_MicroBattleMapPack_v1.0.0.scd",
            "_MapPack_Autumn2026-Part-1_v2.0.0_by_BDFTM.scd",
            "_CustomMission_1p_TermesisCustomMission_v5.0.0_by_bdftm.scd",
            "_Map_6p_OpenPalmsInfiniteMass_v1.0.0.scd",
            "_Map_8p_AZU-Europa-Research-Site_v1.0.0_by_blu-azur.scd",
        ]
        for name in names:
            self.assertIsNotNone(v.FILE_NAME.match(name), name)

    def test_bad_file_names(self):
        for name in ["map.scd", "Forest_v1.0.0.scd", "_Map_Forest_v1.0.0.scd", "_Map_6p_My Map_v1.0.0.scd",
                     "_Map_6p_Forest_1.0.0.scd", "_Map_6p_Forest_v1.0.scd", "_Map_9p_Forest_v1.0.0.scd",
                     "_MapPack_6p_Pack_v1.0.0.scd"]:
            url = f"https://example.com/{name.replace(' ', '%20')}"
            errors = v.check_fields(body(**{"Download URL": url, "Players": "Unknown"}))
            self.assertTrue(errors, name)

    def test_missing_fields_are_reported_together(self):
        errors = v.check_fields(body(**{"Map name": "_No response_", "Author": "", "Map or mappack version": "1.0"}))
        self.assertEqual(len(errors), 3)

    def test_version_must_match_file_name(self):
        errors = v.check_fields(body(**{"Map or mappack version": "2.0.0"}))
        self.assertTrue(any("does not match" in e for e in errors))

    def test_players_must_match_file_name(self):
        errors = v.check_fields(body(Players="8 Players"))
        self.assertTrue(any("must match" in e for e in errors))
        self.assertEqual(v.check_fields(body(Players="Unknown")), [])

    def test_url_rules(self):
        self.assertTrue(v.check_fields(body(**{"Download URL": "http://example.com/_Map_6p_Forest_v1.0.0.scd"})))
        self.assertTrue(v.check_fields(body(**{"Download URL": "https://example.com/_Map_6p_Forest_v1.0.0.scd?dl=1"})))
        self.assertTrue(v.check_fields(body(**{"Download URL": "https://example.com/download"})))

    def test_the_scenario_field_is_filled_automatically_so_its_content_does_not_matter(self):
        for text in ["_No response_", "", "/maps/a/a.txt", "anything at all"]:
            self.assertEqual(v.check_fields(body(**{"Scenario File Paths": text})), [], text)

    def test_agreement_must_be_ticked(self):
        errors = v.check_fields(body(**{"Publication agreement": "- [x] one\n- [ ] two"}))
        self.assertEqual(len(errors), 1)

    def test_carriage_returns_are_ignored(self):
        self.assertEqual(v.check_fields(body().replace("\n", "\r\n")), [])


def other(number, paths, *labels):
    return {"number": number, "body": body(**{"Scenario File Paths": paths}), "labels": [{"name": n} for n in labels]}


class CollisionTests(unittest.TestCase):
    OWN = "/maps/A/A_scenario.lua\n/maps/A/B_scenario.lua"

    def check(self, issues, newer_only=False, hidden=False, number=10):
        return v.check_collisions(body(**{"Scenario File Paths": self.OWN}), number, issues, newer_only, hidden)

    def test_one_shared_path_is_a_collision_even_when_the_maps_have_more_paths(self):
        errors = self.check([other(3, "/maps/A/B_scenario.lua\n/maps/Z/Z_scenario.lua", "verified")])
        self.assertEqual(len(errors), 1)
        self.assertIn("/maps/A/B_scenario.lua", errors[0])
        self.assertIn("#3", errors[0])

    def test_no_shared_path_is_no_collision(self):
        self.assertEqual(self.check([other(3, "/maps/Z/Z_scenario.lua", "verified")]), [])

    def test_a_pack_of_many_paths_does_not_collide_without_a_shared_single_path(self):
        self.assertEqual(self.check([other(3, "/maps/Z/Z_scenario.lua\n/maps/Y/Y_scenario.lua", "verified")]), [])

    def test_case_and_leading_slash_do_not_matter(self):
        self.assertEqual(len(self.check([other(3, "maps/a/a_SCENARIO.lua", "verified")])), 1)

    def test_only_verified_maps_count(self):
        self.assertEqual(self.check([other(3, self.OWN, "pending"), other(4, self.OWN, "invalid")]), [])

    def test_hidden_maps_are_ignored(self):
        self.assertEqual(self.check([other(3, self.OWN, "verified", "hidden")]), [])

    def test_a_hidden_map_is_not_checked(self):
        self.assertEqual(self.check([other(3, self.OWN, "verified")], hidden=True), [])

    def test_the_map_itself_is_ignored(self):
        self.assertEqual(self.check([other(10, self.OWN, "verified")]), [])

    def test_newer_only_keeps_the_older_map(self):
        issues = [other(3, self.OWN, "verified"), other(20, self.OWN, "verified")]
        errors = self.check(issues, newer_only=True)
        self.assertEqual(len(errors), 2)
        self.assertIn("#3", errors[0])
        self.assertNotIn("#20", errors[0])

    def test_every_colliding_owner_is_listed_once_per_path(self):
        errors = self.check([other(3, self.OWN, "verified"), other(4, self.OWN, "verified")])
        self.assertEqual(len(errors), 2)
        self.assertIn("#3, #4", errors[0])


class HashTests(unittest.TestCase):
    SHA = "A" * 64
    MD5 = "B" * 32

    def test_fills_empty_sha_and_adds_missing_md5_after_it(self):
        text = body().replace("### Publication agreement", "### SHA-256 (generated automatically)\n\n_No response_\n\n### Publication agreement")
        result = v.with_hashes(text, self.SHA, self.MD5)
        self.assertEqual(v.value(result, v.SHA_HEADING), self.SHA)
        self.assertEqual(v.value(result, v.MD5_HEADING), self.MD5)
        self.assertLess(result.index(v.SHA_HEADING), result.index(v.MD5_HEADING))
        self.assertLess(result.index(v.MD5_HEADING), result.index("### Publication agreement"))
        self.assertEqual(v.value(result, "Publication agreement"), v.value(text, "Publication agreement"))

    def test_replaces_existing_values(self):
        text = body(**{"SHA-256 (generated automatically)": "C" * 64, "MD5 (generated automatically)": "D" * 32})
        result = v.with_hashes(text, self.SHA, self.MD5)
        self.assertEqual(v.value(result, v.SHA_HEADING), self.SHA)
        self.assertEqual(v.value(result, v.MD5_HEADING), self.MD5)
        self.assertEqual(result.count("### MD5"), 1)

    def test_keep_sha_leaves_an_existing_sha_but_fills_a_missing_one(self):
        text = body(**{"SHA-256 (generated automatically)": "C" * 64})
        self.assertEqual(v.value(v.with_hashes(text, self.SHA, self.MD5, keep_sha=True), v.SHA_HEADING), "C" * 64)
        empty = body(**{"SHA-256 (generated automatically)": "_No response_"})
        self.assertEqual(v.value(v.with_hashes(empty, self.SHA, self.MD5, keep_sha=True), v.SHA_HEADING), self.SHA)

    def test_section_at_the_end_and_missing_sha_section(self):
        text = "### Map name\n\nX\n\n### SHA-256 (generated automatically)\n\n_No response_"
        result = v.with_hashes(text, self.SHA, self.MD5)
        self.assertEqual(v.value(result, v.SHA_HEADING), self.SHA)
        self.assertEqual(v.value(result, v.MD5_HEADING), self.MD5)
        no_sha = v.with_hashes("### Map name\n\nX", self.SHA, self.MD5)
        self.assertEqual(v.value(no_sha, v.SHA_HEADING), self.SHA)
        self.assertEqual(v.value(no_sha, v.MD5_HEADING), self.MD5)

    def test_keeps_windows_line_endings(self):
        text = body().replace("\n", "\r\n")
        result = v.with_hashes(text, self.SHA, self.MD5)
        self.assertNotIn("\n\n", result.replace("\r\n", ""))
        self.assertEqual(v.value(result, v.MD5_HEADING), self.MD5)


class ArchiveTests(unittest.TestCase):
    def make_zip(self, entries):
        handle = tempfile.NamedTemporaryFile(suffix=".scd", delete=False)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        with zipfile.ZipFile(handle.name, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return handle.name

    def test_valid_archive(self):
        path = self.make_zip({"maps/BDFTM_Forest/BDFTM_Forest_scenario.lua": "x", "maps/BDFTM_Forest/a.scmap": "y"})
        self.assertEqual(v.check_archive(body(), path), [])

    def test_scenario_lookup_ignores_case_and_leading_slash(self):
        path = self.make_zip({"Maps/bdftm_forest/bdftm_forest_scenario.LUA": "x"})
        self.assertEqual(v.check_archive(body(), path), [])

    def test_archive_without_a_scenario_in_the_root_maps_folder(self):
        path = self.make_zip({"maps/other/other_save.lua": "x", "uncompiled/maps/other/other_scenario.lua": "x"})
        self.assertTrue(any("no scenario file" in e for e in v.check_archive(body(), path)))

    def test_scenarios_come_from_the_root_maps_folder_only_and_are_sorted(self):
        path = self.make_zip({
            "maps/Zeta/Zeta_scenario.lua": "x", "maps/Alpha/Alpha_scenario.lua": "x", "maps/Alpha/Alpha_save.lua": "x",
            "uncompiled/maps/Alpha/Alpha_scenario.lua": "x", "uncompiled/maps/Other/Other_scenario.lua": "x",
        })
        self.assertEqual(v.find_scenarios(path), ["/maps/Alpha/Alpha_scenario.lua", "/maps/Zeta/Zeta_scenario.lua"])

    def test_scenarios_of_nested_archives_are_used_when_there_is_no_root_maps_folder(self):
        inner = tempfile.NamedTemporaryFile(suffix=".scd", delete=False)
        inner.close()
        self.addCleanup(os.unlink, inner.name)
        with zipfile.ZipFile(inner.name, "w") as archive:
            archive.writestr("maps/Inner/Inner_scenario.lua", "x")
        with open(inner.name, "rb") as handle:
            path = self.make_zip({"pack/Inner.scd": handle.read(), "readme.txt": "x"})
        self.assertEqual(v.find_scenarios(path), ["/maps/Inner/Inner_scenario.lua"])

    def test_scenario_paths_with_unsupported_characters_are_reported(self):
        path = self.make_zip({"maps/My Map/My Map_scenario.lua": "x"})
        self.assertTrue(any("may only use" in e for e in v.check_archive(body(), path)))

    def test_too_many_scenarios(self):
        path = self.make_zip({f"maps/M{i}/M{i}_scenario.lua": "x" for i in range(v.MAX_SCENARIOS + 1)})
        self.assertTrue(any("more than" in e for e in v.check_archive(body(), path)))

    def test_not_an_archive_has_no_scenarios(self):
        handle = tempfile.NamedTemporaryFile(suffix=".scd", delete=False)
        handle.write(b"nope")
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        self.assertEqual(v.find_scenarios(handle.name), [])

    def test_with_scenarios_replaces_the_field_with_one_path_per_line(self):
        text = body(**{"Scenario File Paths": "/maps/typed/by_the_author.lua"})
        result = v.with_scenarios(text, ["/maps/A/A_scenario.lua", "/maps/B/B_scenario.lua"])
        self.assertEqual(v.scenario_paths(result), ["/maps/A/A_scenario.lua", "/maps/B/B_scenario.lua"])
        self.assertEqual(v.value(result, "Map name"), "Forest")

    def test_scenario_inside_nested_scd(self):
        inner = tempfile.NamedTemporaryFile(suffix=".scd", delete=False)
        inner.close()
        self.addCleanup(os.unlink, inner.name)
        with zipfile.ZipFile(inner.name, "w") as archive:
            archive.writestr("maps/BDFTM_Forest/BDFTM_Forest_scenario.lua", "x")
        with open(inner.name, "rb") as handle:
            path = self.make_zip({"_Map_6p_Forest_v1.0.0.scd": handle.read()})
        self.assertEqual(v.check_archive(body(), path), [])

    def test_forbidden_files(self):
        path = self.make_zip({"maps/BDFTM_Forest/BDFTM_Forest_scenario.lua": "x", "install.exe": "MZ"})
        self.assertTrue(any("not allowed" in e for e in v.check_archive(body(), path)))

    def test_unsafe_paths(self):
        path = self.make_zip({"maps/BDFTM_Forest/BDFTM_Forest_scenario.lua": "x", "../evil.lua": "x"})
        self.assertTrue(any("unsafe" in e for e in v.check_archive(body(), path)))

    def test_not_an_archive(self):
        handle = tempfile.NamedTemporaryFile(suffix=".scd", delete=False)
        handle.write(b"<html>not a map</html>")
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        self.assertTrue(any("not a valid" in e for e in v.check_archive(body(), handle.name)))


if __name__ == "__main__":
    unittest.main()
