from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_canonical_base_runtime_exists(self):
        runtime_file = PROJECT_ROOT / "operator_assist_runtime" / "base_runtime.py"
        self.assertTrue(runtime_file.exists(), f"Missing canonical runtime: {runtime_file}")

    def test_legacy_shim_exists(self):
        shim_file = PROJECT_ROOT / "backups" / "operator_assist_chat_bridge_base.py"
        self.assertTrue(shim_file.exists(), f"Missing compatibility shim: {shim_file}")

    def test_no_hardcoded_user_specific_paths_in_key_entry_points(self):
        files_to_check = [
            PROJECT_ROOT / "operator_assist.py",
            PROJECT_ROOT / "operator_assist_chat_bridge_v5_base.py",
            PROJECT_ROOT / "operator_assist_chat_window_test.py",
            PROJECT_ROOT / "Run-Operator-Assist.cmd",
            PROJECT_ROOT / "Run-Operator-Assist.vbs",
            PROJECT_ROOT / "Run-Operator-Assist.ps1",
            PROJECT_ROOT / "Setup-From-Git.cmd",
            PROJECT_ROOT / "Run-Operator-Assist-ChatWindow-Test.cmd",
            PROJECT_ROOT / "Run-Operator-Assist-ChatWindow-Test.vbs",
            PROJECT_ROOT / "Run-Operator-Assist-ChatWindow-Test.ps1",
            PROJECT_ROOT / "Run-VoiceNotes.ps1",
            PROJECT_ROOT / "Run-Speaker-Text.ps1",
        ]
        banned_fragments = [
            "C:\\Users\\79615",
            "D:/OPERATOR_ASSIST",
            "D:\\OPERATOR_ASSIST",
        ]

        offenders = []
        for file_path in files_to_check:
            content = file_path.read_text(encoding="utf-8")
            for banned in banned_fragments:
                if banned in content:
                    offenders.append((file_path.name, banned))

        self.assertEqual([], offenders, f"Found machine-specific paths: {offenders}")

    def test_pyproject_has_repository_name(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "operator-assist"', pyproject)
        self.assertIn('Repository = "https://github.com/YuryGorshkov/OPERATOR_ASSIST"', pyproject)
        self.assertIn('[project.optional-dependencies]', pyproject)
        self.assertIn('"pyinstaller>=6.10,<7"', pyproject)

    def test_version_is_consistent_across_runtime_and_packaging(self):
        version_sources = {
            "pyproject": (PROJECT_ROOT / "pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
            "installer": (
                PROJECT_ROOT / "packaging" / "inno" / "OperatorAssist.iss",
                r'^\s*#define MyAppVersion\s+"([^"]+)"',
            ),
            "entry_wrapper": (
                PROJECT_ROOT / "operator_assist.py",
                r'^WRAPPER_VERSION\s*=\s*"([^"]+)"',
            ),
            "runtime_wrapper": (
                PROJECT_ROOT / "operator_assist_chat_bridge_v5_base.py",
                r'^WRAPPER_VERSION\s*=\s*"([^"]+)"',
            ),
            "base_runtime": (
                PROJECT_ROOT / "operator_assist_runtime" / "base_runtime.py",
                r'^APP_VERSION\s*=\s*"([^"]+)"',
            ),
        }
        versions = {}
        for label, (path, pattern) in version_sources.items():
            match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
            self.assertIsNotNone(match, f"Missing version in {path}")
            versions[label] = match.group(1)

        self.assertEqual(1, len(set(versions.values())), versions)

    def test_packaging_assets_exist(self):
        expected_files = [
            PROJECT_ROOT / ".github" / "workflows" / "ci.yml",
            PROJECT_ROOT / ".github" / "workflows" / "release.yml",
            PROJECT_ROOT / "packaging" / "pyinstaller" / "operator_assist.spec",
            PROJECT_ROOT / "packaging" / "inno" / "OperatorAssist.iss",
            PROJECT_ROOT / "scripts" / "Build-Release.ps1",
            PROJECT_ROOT / "operator_assist_runtime" / "runtime_paths.py",
        ]

        missing = [str(path) for path in expected_files if not path.exists()]
        self.assertEqual([], missing, f"Missing packaging assets: {missing}")

    def test_pause_recognition_runtime_is_explicitly_bundled(self):
        spec = (PROJECT_ROOT / "packaging" / "pyinstaller" / "operator_assist.spec").read_text(
            encoding="utf-8"
        )

        self.assertIn('"operator_assist_runtime.pause_recognition"', spec)

    def test_installer_preserves_editable_config_files(self):
        installer = (
            PROJECT_ROOT / "packaging" / "inno" / "OperatorAssist.iss"
        ).read_text(encoding="utf-8")

        for file_name in (
            "technical_terms.json",
            "custom_terms.txt",
            "chatgpt_prompt_template.txt",
        ):
            matching_lines = [
                line for line in installer.splitlines()
                if line.startswith(
                    f'Source: "{{#MyPortableRoot}}\\config\\{file_name}"'
                )
            ]
            self.assertEqual(1, len(matching_lines), (file_name, matching_lines))
            self.assertIn("onlyifdoesntexist", matching_lines[0])

    def test_branding_assets_exist(self):
        expected_files = [
            PROJECT_ROOT / "assets" / "logo-enot.png",
            PROJECT_ROOT / "assets" / "logo-enot-72.png",
            PROJECT_ROOT / "assets" / "logo-enot-96.png",
            PROJECT_ROOT / "assets" / "logo-enot-128.png",
            PROJECT_ROOT / "assets" / "logo-enot-256.png",
            PROJECT_ROOT / "assets" / "operator_assist.ico",
        ]

        missing = [str(path) for path in expected_files if not path.exists()]
        self.assertEqual([], missing, f"Missing branding assets: {missing}")

    def test_key_docs_exist(self):
        expected_files = [
            PROJECT_ROOT / "docs" / "architecture.md",
            PROJECT_ROOT / "docs" / "case-study.md",
            PROJECT_ROOT / "docs" / "demo-script.md",
            PROJECT_ROOT / "docs" / "deployment.md",
            PROJECT_ROOT / "docs" / "first-launch.md",
            PROJECT_ROOT / "docs" / "install-from-git.md",
            PROJECT_ROOT / "docs" / "install-from-release.md",
            PROJECT_ROOT / "docs" / "known-issues.md",
            PROJECT_ROOT / "docs" / "recognition-lab.md",
            PROJECT_ROOT / "docs" / "smoke-checklist.md",
        ]

        missing = [str(path) for path in expected_files if not path.exists()]
        self.assertEqual([], missing, f"Missing key documentation files: {missing}")

    def test_recognition_lab_keeps_private_data_out_of_git(self):
        ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for path in ("/asr-lab-data/", "/asr-lab-reports/", "/asr-lab-checkpoints/",
                     "/examples/recognition-lab/audio/", "/examples/recognition-lab/references/"):
            self.assertIn(path, ignored)

    def test_ci_initializes_runner_cache_only_inside_a_step(self):
        ci = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        job_env = ci.split("    env:\n", 1)[1].split("    steps:", 1)[0]
        self.assertNotIn("${{ runner.", job_env)
        self.assertIn("$env:RUNNER_TEMP", ci)
        self.assertIn("$env:GITHUB_ENV", ci)


if __name__ == "__main__":
    unittest.main()
