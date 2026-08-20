from pathlib import Path
import sys
import unittest
from unittest import mock

from operator_assist_runtime.runtime_paths import application_root, bundle_root, is_frozen, runtime_layout


class RuntimePathTests(unittest.TestCase):
    def test_source_mode_paths_use_anchor_file(self):
        anchor = Path(r"D:\OPERATOR_ASSIST\operator_assist_runtime\base_runtime.py")

        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertFalse(is_frozen())
            self.assertEqual(anchor.parent, bundle_root(anchor))
            self.assertEqual(anchor.parents[1], application_root(anchor, levels_up=1))

    def test_frozen_mode_uses_executable_and_meipass(self):
        anchor = Path(r"D:\OPERATOR_ASSIST\operator_assist.py")

        with mock.patch.object(sys, "frozen", True, create=True), \
            mock.patch.object(sys, "_MEIPASS", r"C:\Temp\OPASSIST_BUNDLE", create=True), \
            mock.patch.object(sys, "executable", r"C:\Apps\OPERATOR_ASSIST\OPERATOR_ASSIST.exe", create=True):
            self.assertTrue(is_frozen())
            self.assertEqual(Path(r"C:\Temp\OPASSIST_BUNDLE"), bundle_root(anchor))
            self.assertEqual(Path(r"C:\Apps\OPERATOR_ASSIST"), application_root(anchor))

    def test_application_root_rejects_negative_levels(self):
        anchor = Path(r"D:\OPERATOR_ASSIST\operator_assist.py")

        with mock.patch.object(sys, "frozen", False, create=True):
            with self.assertRaises(ValueError):
                application_root(anchor, levels_up=-1)

    def test_source_layout_keeps_editable_files_at_project_root(self):
        root = Path(r"D:\OPERATOR_ASSIST")
        layout = runtime_layout(root, bundle_dir=root / "_bundle", frozen=False)

        self.assertFalse(layout["packaged"])
        self.assertEqual(root, layout["base_dir"])
        self.assertEqual(root, layout["data_dir"])
        self.assertEqual(root, layout["config_dir"])
        self.assertEqual(root, layout["support_dir"])
        self.assertEqual(root / "assets", layout["assets_dir"])
        self.assertEqual(root / "models", layout["models_dir"])
        self.assertEqual(root / "transcripts", layout["transcripts_dir"])
        self.assertEqual(root / "scripts" / "paste_to_chat_window.vbs", layout["bridge_script_path"])

    def test_frozen_layout_separates_app_files_from_user_data(self):
        install_root = Path(r"E:\OPERATOR_ASSIST_FRESH")
        bundle_root_path = Path(r"C:\Temp\OPERATOR_ASSIST_BUNDLE")
        layout = runtime_layout(install_root, bundle_dir=bundle_root_path, frozen=True)

        self.assertTrue(layout["packaged"])
        self.assertEqual(install_root / "data", layout["data_dir"])
        self.assertEqual(install_root / "config", layout["config_dir"])
        self.assertEqual(install_root / "support", layout["support_dir"])
        self.assertEqual(bundle_root_path / "assets", layout["assets_dir"])
        self.assertEqual(install_root / "data" / "models", layout["models_dir"])
        self.assertEqual(install_root / "data" / "logs", layout["logs_dir"])
        self.assertEqual(install_root / "data" / "transcripts", layout["transcripts_dir"])
        self.assertEqual(install_root / "config" / "technical_terms.json", layout["technical_terms_path"])
        self.assertEqual(install_root / "support" / "scripts" / "paste_to_chat_window.vbs", layout["bridge_script_path"])


if __name__ == "__main__":
    unittest.main()
