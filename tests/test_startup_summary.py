import unittest

from operator_assist_runtime.startup_readiness import (
    build_model_loading_status,
    build_startup_summary,
    format_duration_short,
)


class StartupSummaryTests(unittest.TestCase):
    def test_missing_model_requires_action(self):
        summary = build_startup_summary(
            model_loading=False,
            active_model_name="",
            existing_model_names=[],
            model_error_text="",
            mic_selected="1: Microphone",
            speaker_selected="2: Stereo Mix",
            settings_exists=False,
        )

        self.assertEqual("Нужна модель распознавания", summary["title"])
        self.assertIn("папку с моделями", summary["hint"])
        self.assertIn("в папку с моделями", summary["model_line"])
        self.assertFalse(summary["ready"])

    def test_loaded_model_and_devices_are_ready(self):
        summary = build_startup_summary(
            model_loading=False,
            active_model_name="vosk-model-ru-0.42",
            existing_model_names=["vosk-model-ru-0.42"],
            model_error_text="",
            mic_selected="1: Microphone (Realtek)",
            speaker_selected="WASAPI loopback: Speakers",
            settings_exists=True,
        )

        self.assertEqual("Готово к запуску", summary["title"])
        self.assertIn("загружена", summary["model_line"])
        self.assertIn("сохраняются", summary["settings_line"])
        self.assertTrue(summary["ready"])

    def test_model_error_has_priority(self):
        summary = build_startup_summary(
            model_loading=False,
            active_model_name="",
            existing_model_names=["vosk-model-ru-0.42"],
            model_error_text="bad archive structure",
            mic_selected="1: Microphone",
            speaker_selected="2: Stereo Mix",
            settings_exists=True,
        )

        self.assertEqual("Ошибка загрузки модели", summary["title"])
        self.assertIn("не открылась", summary["model_line"])
        self.assertFalse(summary["ready"])

    def test_speaker_only_mode_does_not_require_a_microphone(self):
        summary = build_startup_summary(
            model_loading=False,
            active_model_name="vosk-model-ru-0.42",
            existing_model_names=["vosk-model-ru-0.42"],
            model_error_text="",
            mic_selected="",
            speaker_selected="2: Stereo Mix",
            settings_exists=True,
            mic_required=False,
            speaker_required=True,
        )

        self.assertTrue(summary["ready"])
        self.assertIn("канал оператора выключен", summary["mic_line"])

    def test_format_duration_short_shows_minutes_and_seconds(self):
        self.assertEqual("0:37", format_duration_short(37))
        self.assertEqual("2:05", format_duration_short(125))

    def test_build_model_loading_status_mentions_elapsed_and_expected_window(self):
        status = build_model_loading_status(
            phase="Открываю модель",
            model_name="vosk-model-ru-0.42",
            elapsed_seconds=42,
            attempt_index=1,
            attempt_total=2,
        )

        self.assertIn("Попытка 1/2", status)
        self.assertIn("0:42", status)
        self.assertIn("20-180 с", status)


if __name__ == "__main__":
    unittest.main()
