import time
import unittest

from operator_assist_runtime import base_runtime


class ModelLoadingPolicyTests(unittest.TestCase):
    def _app_for_route(self, *, mic_enabled, speaker_enabled, speaker_mode):
        app = base_runtime.OperatorAssistApp.__new__(base_runtime.OperatorAssistApp)
        app._capture_mic_enabled = lambda: mic_enabled
        app._capture_speaker_enabled = lambda: speaker_enabled
        app._current_speaker_mode_key = lambda: speaker_mode
        return app

    def test_whisper_only_route_does_not_require_vosk(self):
        app = self._app_for_route(
            mic_enabled=False,
            speaker_enabled=True,
            speaker_mode=base_runtime.SPEAKER_MODE_PRECISE,
        )

        self.assertFalse(app._requires_vosk_model())

    def test_operator_channel_still_requires_vosk(self):
        app = self._app_for_route(
            mic_enabled=True,
            speaker_enabled=True,
            speaker_mode=base_runtime.SPEAKER_MODE_PRECISE,
        )

        self.assertTrue(app._requires_vosk_model())

    def test_stable_speaker_route_still_requires_vosk(self):
        app = self._app_for_route(
            mic_enabled=False,
            speaker_enabled=True,
            speaker_mode=base_runtime.SPEAKER_MODE_STABLE,
        )

        self.assertTrue(app._requires_vosk_model())

    def test_whisper_loading_keeps_startup_progress_visible(self):
        class FakeVar:
            def __init__(self):
                self.value = ""

            def set(self, value):
                self.value = value

        class FakeProgress:
            def __init__(self):
                self.running = False

            def start(self, _interval):
                self.running = True

            def stop(self):
                self.running = False

        class FakeFrame:
            def __init__(self):
                self.visible = False

            def grid(self):
                self.visible = True

            def grid_remove(self):
                self.visible = False

        app = base_runtime.OperatorAssistApp.__new__(base_runtime.OperatorAssistApp)
        app.setup_loading_frame = FakeFrame()
        app.setup_loading_progress = FakeProgress()
        app.setup_loading_var = FakeVar()
        app.status_var = FakeVar()
        app.model_loading_progress_running = False
        app.model_loading = False
        app.model_loading_started_at = 0.0
        app.precise_engine_loading = True
        app.precise_engine_load_started_at = time.monotonic() - 5.0
        app.model_loading_phase = "Открываю Whisper (cuda/float16)"
        app.model_loading_target_name = "large-v3"
        app.model_loading_attempt_index = 1
        app.model_loading_attempt_total = 3

        app._sync_model_loading_ui()

        self.assertTrue(app.setup_loading_frame.visible)
        self.assertTrue(app.setup_loading_progress.running)
        self.assertIn("large-v3", app.setup_loading_var.value)
        self.assertIn("Прошло", app.setup_loading_var.value)
        self.assertTrue(app.status_var.value.startswith("Загружаю точный режим"))


if __name__ == "__main__":
    unittest.main()
