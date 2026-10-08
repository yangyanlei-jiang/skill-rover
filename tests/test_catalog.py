from common import Fixture

class CatalogTests(Fixture):
    def test_multiline_metadata_and_same_name_keep_distinct_identities(self):
        catalog = self.module("catalog")
        a = self.skill()
        b = self.base / "second"
        b.mkdir()
        (b / "SKILL.md").write_text("---\nname: pdf-extract\ndescription: >-\n  Extract PDF\n  tables.\n---\n", encoding="utf-8")
        result = catalog.scan([a, b])
        self.assertEqual(len(result["skills"]), 2)
        self.assertEqual(result["skills"][1]["description"], "Extract PDF tables.")
        self.assertNotEqual(result["skills"][0]["path"], result["skills"][1]["path"])

    def test_invocation_controls_are_preserved(self):
        catalog = self.module("catalog")
        a = self.skill(extra="disable-model-invocation: true\n")
        self.assertFalse(catalog.read_skill(a)["implicit"])
        b = self.skill("codex-skill")
        (b / "agents").mkdir()
        (b / "agents" / "openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
        self.assertFalse(catalog.read_skill(b)["implicit"])

    def test_malformed_yaml_and_missing_description_are_diagnostics(self):
        catalog = self.module("catalog")
        a = self.skill()
        (a / "SKILL.md").write_text("---\nname: bad\ndescription: [\n---")
        result = catalog.scan([self.base])
        self.assertEqual(result["skills"], [])
        self.assertEqual(len(result["errors"]), 1)

    def test_root_aliases_are_deduplicated(self):
        catalog = self.module("catalog")
        a = self.skill()
        link = self.base / "alias"
        link.symlink_to(a, target_is_directory=True)
        self.assertEqual(len(catalog.scan([a, link])["skills"]), 1)

    def test_bundle_digest_covers_supporting_scripts_and_rejects_symlinks(self):
        catalog = self.module("catalog")
        a = self.skill()
        digest = catalog.bundle_digest(a)
        (a / "helper.py").write_text("print('one')")
        self.assertNotEqual(catalog.bundle_digest(a), digest)
        (a / "escape").symlink_to(self.base)
        with self.assertRaises(ValueError):
            catalog.bundle_digest(a)

