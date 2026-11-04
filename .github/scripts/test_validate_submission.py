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

    def test_scenario_paths(self):
        multi = "/maps/a/a_scenario.lua\n/maps/a/b_scenario.lua"
        self.assertEqual(v.check_fields(body(**{"Scenario File Paths": multi})), [])
        self.assertEqual(v.check_fields(body(**{"Scenario File Paths": "/maps/a/a.lua;/maps/a/b.lua"})), [])
        for bad in ["/maps/a/a.txt", "maps_only.lua", "/other/a.lua", "/maps/../a.lua", "/maps/a/a.lua\n/maps/A/A.lua"]:
            self.assertTrue(v.check_fields(body(**{"Scenario File Paths": bad})), bad)

    def test_agreement_must_be_ticked(self):
        errors = v.check_fields(body(**{"Publication agreement": "- [x] one\n- [ ] two"}))
        self.assertEqual(len(errors), 1)

    def test_carriage_returns_are_ignored(self):
        self.assertEqual(v.check_fields(body().replace("\n", "\r\n")), [])


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

    def test_missing_scenario(self):
        path = self.make_zip({"maps/other/other_scenario.lua": "x"})
        self.assertTrue(any("not found" in e for e in v.check_archive(body(), path)))

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
