from pathlib import Path
import sys
import unittest
from unittest import mock

from operator_assist_runtime.runtime_paths import application_root, bundle_root, is_frozen


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


if __name__ == "__main__":
    unittest.main()
