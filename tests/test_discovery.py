import io
import stat
import zipfile
from common import Fixture

class DiscoveryTests(Fixture):
    def archive(self, files):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for name, body in files:
                archive.writestr(name, body)
        return data.getvalue()

    def test_extract_only_selected_skill_and_report_metadata(self):
        github = self.module("github")
        data = self.archive([("repo-sha/skills/pdf/SKILL.md", "---\nname: pdf\ndescription: Create PDF.\n---\n"),
                             ("repo-sha/README.md", "not copied")])
        target = self.base / "download"
        result = github.extract_skill(data, "skills/pdf", target)
        self.assertEqual(result["name"], "pdf")
        self.assertFalse((target / "README.md").exists())

    def test_archive_traversal_and_symlink_are_rejected_without_output(self):
        github = self.module("github")
        for name in ["repo/../escape", "/tmp/escape", "repo/skills/pdf/../../escape", "repo/evil\\file"]:
            target = self.base / "download"
            with self.assertRaises(ValueError):
                github.extract_skill(self.archive([(name, "bad")]), "", target)
            self.assertFalse(target.exists())
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            info = zipfile.ZipInfo("repo/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "/tmp")
        with self.assertRaises(ValueError):
            github.extract_skill(data.getvalue(), "", self.base / "download")

    def test_invalid_subdirectory_and_existing_destination_preserve_files(self):
        github = self.module("github")
        target = self.base / "exists"
        target.mkdir()
        (target / "keep").write_text("user data")
        data = self.archive([("repo/SKILL.md", "---\nname: x\ndescription: X\n---")])
        with self.assertRaises(ValueError):
            github.extract_skill(data, "", target)
        self.assertEqual((target / "keep").read_text(), "user data")
        with self.assertRaises(ValueError):
            github.extract_skill(data, "../bad", self.base / "new")

    def test_non_skill_archive_is_not_installed(self):
        github = self.module("github")
        target = self.base / "download"
        with self.assertRaises(ValueError):
            github.extract_skill(self.archive([("repo/README.md", "hello")]), "", target)
        self.assertFalse(target.exists())

    def test_duplicate_paths_and_oversized_bundle_are_rejected(self):
        github = self.module("github")
        manifest = "---\nname: x\ndescription: X\n---"
        data = self.archive([("repo/SKILL.md", manifest), ("repo/big", "x" * (16 * 1024 * 1024 + 1))])
        with self.assertRaises(ValueError):
            github.extract_skill(data, "", self.base / "download")

    def test_repository_input_cannot_change_api_host(self):
        github = self.module("github")
        for repo in ["https://evil.test/repo", "a/b/c", "../b", "owner/repo?x=y"]:
            with self.assertRaises(ValueError):
                github.validate_repository(repo)

    def test_executable_resource_retains_only_safe_executable_permissions(self):
        github = self.module("github")
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("repo/SKILL.md", "---\nname: x\ndescription: X\n---")
            info = zipfile.ZipInfo("repo/tool.sh")
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o4755) << 16
            archive.writestr(info, "#!/bin/sh\nexit 0\n")
        target = self.base / "download"
        github.extract_skill(data.getvalue(), "", target)
        self.assertEqual((target / "tool.sh").stat().st_mode & 0o7777, 0o755)
