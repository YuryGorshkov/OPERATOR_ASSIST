from pathlib import Path
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

    def test_packaging_assets_exist(self):
        expected_files = [
            PROJECT_ROOT / "packaging" / "pyinstaller" / "operator_assist.spec",
            PROJECT_ROOT / "packaging" / "inno" / "OperatorAssist.iss",
            PROJECT_ROOT / "scripts" / "Build-Release.ps1",
            PROJECT_ROOT / "operator_assist_runtime" / "runtime_paths.py",
        ]

        missing = [str(path) for path in expected_files if not path.exists()]
        self.assertEqual([], missing, f"Missing packaging assets: {missing}")

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
            PROJECT_ROOT / "docs" / "deployment.md",
            PROJECT_ROOT / "docs" / "first-launch.md",
            PROJECT_ROOT / "docs" / "known-issues.md",
        ]

        missing = [str(path) for path in expected_files if not path.exists()]
        self.assertEqual([], missing, f"Missing key documentation files: {missing}")


if __name__ == "__main__":
    unittest.main()
