import unittest

from operator_assist_runtime.base_runtime import build_startup_summary


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
        self.assertIn("папку models", summary["hint"])
        self.assertIn("положите в папку models", summary["model_line"])
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


if __name__ == "__main__":
    unittest.main()
