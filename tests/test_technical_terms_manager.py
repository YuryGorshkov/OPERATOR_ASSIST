import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from operator_assist_runtime.technical_terms import TechnicalTermsManager
from operator_assist_runtime.text_utils import (
    are_exact_duplicates,
    normalize_name,
    short_text,
)


def build_logger():
    logger = logging.getLogger("operator_assist.tests.technical_terms")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


class TechnicalTermsManagerTests(unittest.TestCase):
    def test_global_replacements_apply_without_modes(self):
        with TemporaryDirectory() as temp_dir:
            terms_path = Path(temp_dir) / "technical_terms.json"
            logger = build_logger()

            manager = TechnicalTermsManager(
                get_terms_path=lambda: terms_path,
                get_logger=lambda: logger,
                normalize_name=normalize_name,
                short_text=short_text,
                default_payload_factory=lambda: {
                    "enabled": True,
                    "replacements": {
                        "эс кью эль": "SQL",
                        "пи эйч пи": "PHP",
                    },
                },
            )

            self.assertEqual("SQL и PHP", manager.apply("эс кью эль и пи эйч пи"))

    def test_mode_specific_replacements_require_active_mode(self):
        with TemporaryDirectory() as temp_dir:
            terms_path = Path(temp_dir) / "technical_terms.json"
            logger = build_logger()

            manager = TechnicalTermsManager(
                get_terms_path=lambda: terms_path,
                get_logger=lambda: logger,
                normalize_name=normalize_name,
                short_text=short_text,
                default_payload_factory=lambda: {
                    "enabled": True,
                    "replacements": {
                        "джейсон": "JSON",
                    },
                    "modes": {
                        "it_mode": {
                            "label": "IT режим",
                            "description": "Проверка терминов",
                            "replacements": {
                                "ларавел": "Laravel",
                                "постгрес": "PostgreSQL",
                            },
                        }
                    },
                },
            )

            self.assertEqual("ларавел и JSON", manager.apply("ларавел и джейсон"))
            self.assertEqual(("it_mode",), manager.set_active_modes(("it_mode",)))
            self.assertEqual("Laravel и JSON", manager.apply("ларавел и джейсон"))
            self.assertEqual(
                "PostgreSQL",
                manager.apply("постгрес", active_modes=("it_mode",)),
            )

    def test_file_payload_overrides_defaults(self):
        with TemporaryDirectory() as temp_dir:
            terms_path = Path(temp_dir) / "technical_terms.json"
            logger = build_logger()
            terms_path.write_text(
                '{\n'
                '  "enabled": true,\n'
                '  "replacements": {\n'
                '    "редис": "Redis"\n'
                "  }\n"
                "}\n",
                encoding="utf-8",
            )

            manager = TechnicalTermsManager(
                get_terms_path=lambda: terms_path,
                get_logger=lambda: logger,
                normalize_name=normalize_name,
                short_text=short_text,
                default_payload_factory=lambda: {
                    "enabled": True,
                    "replacements": {
                        "редис": "SHOULD_NOT_APPEAR",
                    },
                },
            )

            payload = manager.load(force=True)
            self.assertEqual(str(terms_path), payload["source"])
            self.assertEqual("Redis", manager.apply("редис"))


class TextUtilsTests(unittest.TestCase):
    def test_short_text_truncates_cleanly(self):
        self.assertEqual("alpha beta...", short_text("alpha beta gamma delta", limit=13))

    def test_are_exact_duplicates_respects_min_chars(self):
        self.assertTrue(are_exact_duplicates("Laravel framework", "laravel   framework"))
        self.assertFalse(are_exact_duplicates("php", "PHP"))


if __name__ == "__main__":
    unittest.main()
