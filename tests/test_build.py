from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build


class PublicSiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.workspace = Path(self.temporary_directory.name)
        self.root = self.workspace / "public-site"
        for directory in ("assets", "content", "templates"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)

        (self.root / "assets" / "app.js").write_text("", encoding="utf-8")
        (self.root / "assets" / "styles.css").write_text("", encoding="utf-8")
        (self.root / "assets" / "favicon.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
        )
        (self.root / "templates" / "index.html").write_text(
            '<link rel="icon" href="{{ base_url }}assets/favicon.svg"> '
            "{{ card_count }} cards",
            encoding="utf-8",
        )
        (self.root / "templates" / "note.html").write_text(
            "{{ note.title }}: {{ note.html }}", encoding="utf-8"
        )
        (self.root / "templates" / "404.html").write_text(
            "Not found: {{ site.name }}", encoding="utf-8"
        )
        (self.root / "site-config.json").write_text(
            json.dumps(
                {
                    "name": "Test Lexicon",
                    "short_name": "Lexicon",
                    "description": "Test site",
                }
            ),
            encoding="utf-8",
        )
        (self.root / "content" / "vocabulary.md").write_text(
            "# Vocabulary\n\nA safe fixture.", encoding="utf-8"
        )
        self.valid_note = {
            "slug": "vocabulary",
            "title": "Vocabulary",
            "kind": "vocabulary",
            "content_file": "content/vocabulary.md",
            "summary_cn": "测试词卡",
            "summary_en": "A test card.",
            "metadata": {
                "lemma": "vocabulary",
                "forms": [],
                "pos": ["noun"],
                "study_mode": "production",
                "mastery": "new",
                "context_status": "ready",
            },
        }
        self.write_manifest([self.valid_note])

    @staticmethod
    def snapshot_tree(root: Path):
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    def write_manifest(self, notes):
        (self.root / "content" / "manifest.json").write_text(
            json.dumps({"notes": notes}, ensure_ascii=False), encoding="utf-8"
        )

    def create_directory_link(self, link: Path, target: Path):
        symlink_failure = None
        try:
            link.symlink_to(target, target_is_directory=True)
            return
        except (NotImplementedError, OSError) as error:
            symlink_failure = error
            if os.name != "nt":
                self.skipTest(f"directory symlinks are unavailable: {error}")

        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            self.skipTest(
                "directory links are unavailable: "
                f"symlink={symlink_failure}; junction={completed.stderr.strip()}"
            )

    def test_build_produces_safe_static_output(self):
        output = self.root / "dist"
        result = build.build_site(self.root, output, "/test-site/")
        self.assertEqual(result["cards"], 1)
        self.assertTrue((output / "index.html").is_file())
        self.assertTrue((output / "vocabulary.html").is_file())
        self.assertTrue((output / "assets" / "favicon.svg").is_file())
        self.assertIn(
            '/test-site/assets/favicon.svg',
            (output / "index.html").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (output / build.BUILD_MARKER_NAME).read_text(encoding="utf-8"),
            build.BUILD_MARKER_CONTENT,
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in output.rglob("*")
            if path.is_file()
        )
        for forbidden in ("GITHUB_PERSONAL_ACCESS_TOKEN", "PRIVATE KEY"):
            self.assertNotIn(forbidden, combined)

    def test_external_temporary_output_is_allowed(self):
        output = self.workspace / "external-build"
        output.mkdir()
        result = build.build_site(self.root, output, "/")
        self.assertEqual(Path(result["output"]), output.resolve())
        self.assertTrue((output / "index.html").is_file())
        self.assertTrue((output / build.BUILD_MARKER_NAME).is_file())

        stale = output / "stale.txt"
        stale.write_text("remove on marked rebuild", encoding="utf-8")
        build.build_site(self.root, output, "/")
        self.assertFalse(stale.exists())

    def test_nonstandard_internal_directory_is_never_deleted(self):
        output = self.root / "site-output"
        output.mkdir()
        marker = output / "keep-me.txt"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "project_root/dist"):
            build.build_site(self.root, output, "/")
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_unmarked_external_nonempty_directory_is_never_deleted(self):
        output = self.workspace / "existing-external"
        output.mkdir()
        marker = output / "keep-me.txt"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "build marker"):
            build.build_site(self.root, output, "/")
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_project_root_and_parent_are_never_deleted(self):
        marker = self.root / "keep-me.txt"
        marker.write_text("preserve", encoding="utf-8")
        for output in (self.root, self.root.parent):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, "project root|ancestors"):
                    build.build_site(self.root, output, "/")
                self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_filesystem_root_is_rejected_without_deletion(self):
        filesystem_root = Path(self.root.anchor)
        with self.assertRaisesRegex(ValueError, "filesystem root"):
            build._validate_output_path(self.root, filesystem_root)

    def test_project_source_directory_is_not_an_output_directory(self):
        with self.assertRaisesRegex(ValueError, "dedicated build directory"):
            build.build_site(self.root, self.root / "content", "/")
        self.assertTrue((self.root / "content" / "manifest.json").is_file())

    def test_failed_rebuild_preserves_the_previous_complete_site(self):
        output = self.root / "dist"
        build.build_site(self.root, output, "/")
        expected = self.snapshot_tree(output)
        valid_config = (self.root / "site-config.json").read_text(encoding="utf-8")
        valid_template = (self.root / "templates" / "index.html").read_text(
            encoding="utf-8"
        )

        cases = {
            "kind": lambda: self.write_manifest(
                [{key: value for key, value in self.valid_note.items() if key != "kind"}]
            ),
            "metadata": lambda: self.write_manifest(
                [{**self.valid_note, "metadata": None}]
            ),
            "config": lambda: (self.root / "site-config.json").write_text(
                "{}", encoding="utf-8"
            ),
            "template": lambda: (self.root / "templates" / "index.html").write_text(
                "{% if", encoding="utf-8"
            ),
        }
        for name, corrupt in cases.items():
            with self.subTest(name=name):
                self.write_manifest([self.valid_note])
                (self.root / "site-config.json").write_text(
                    valid_config, encoding="utf-8"
                )
                (self.root / "templates" / "index.html").write_text(
                    valid_template, encoding="utf-8"
                )
                corrupt()
                with self.assertRaises(Exception):
                    build.build_site(self.root, output, "/")
                self.assertEqual(self.snapshot_tree(output), expected)

        self.assertFalse(any(self.root.glob(".dist.staging-*")))
        self.assertFalse(any(self.root.glob(".dist.backup-*")))

    def test_staging_write_failure_preserves_the_previous_complete_site(self):
        output = self.root / "dist"
        build.build_site(self.root, output, "/")
        expected = self.snapshot_tree(output)

        with mock.patch.object(
            build.shutil, "copytree", side_effect=RuntimeError("copy failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "copy failed"):
                build.build_site(self.root, output, "/")

        self.assertEqual(self.snapshot_tree(output), expected)
        self.assertFalse(any(self.root.glob(".dist.staging-*")))
        self.assertFalse(any(self.root.glob(".dist.backup-*")))

    def test_symlink_or_junction_output_escape_is_rejected(self):
        target = self.workspace / "outside-target"
        target.mkdir()
        marker = target / "keep-me.txt"
        marker.write_text("preserve", encoding="utf-8")
        output = self.root / "dist"
        self.create_directory_link(output, target)

        with self.assertRaisesRegex(ValueError, "symlink or junction"):
            build.build_site(self.root, output, "/")
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_invalid_and_duplicate_slugs_are_rejected(self):
        invalid_cases = [
            [{**self.valid_note, "slug": "../escape"}],
            [self.valid_note, dict(self.valid_note)],
        ]
        for notes in invalid_cases:
            with self.subTest(notes=notes):
                self.write_manifest(notes)
                with self.assertRaisesRegex(ValueError, "slug"):
                    build.build_site(self.root, self.root / "dist", "/")

    def test_content_file_must_be_relative_and_stay_inside_content(self):
        outside = self.root / "private.md"
        outside.write_text("private", encoding="utf-8")
        invalid_paths = [
            str(outside.resolve()),
            "content/../private.md",
        ]
        for content_file in invalid_paths:
            with self.subTest(content_file=content_file):
                self.write_manifest([{**self.valid_note, "content_file": content_file}])
                with self.assertRaisesRegex(ValueError, "content_file"):
                    build.build_site(self.root, self.root / "dist", "/")

    def test_content_symlink_escape_is_rejected(self):
        outside = self.workspace / "private-source"
        outside.mkdir()
        (outside / "private.md").write_text("private", encoding="utf-8")
        link = self.root / "content" / "linked-private"
        self.create_directory_link(link, outside)

        self.write_manifest(
            [{**self.valid_note, "content_file": "content/linked-private/private.md"}]
        )
        with self.assertRaisesRegex(ValueError, "escapes content"):
            build.build_site(self.root, self.root / "dist", "/")

    def test_output_file_guard_rejects_traversal(self):
        output = self.root / "dist"
        output.mkdir()
        with self.assertRaisesRegex(ValueError, "escapes the build directory"):
            build._safe_output_path(output.resolve(), "../outside.html")

    def test_normalize_base_url_supports_root_and_project_pages(self):
        cases = {
            "": "/",
            "/": "/",
            "repo": "/repo/",
            "/repo/": "/repo/",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(build.normalize_base_url(value), expected)


if __name__ == "__main__":
    unittest.main()
