import inspect
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import operator_assist_chat_bridge_v3_base as chat_runtime
import operator_assist_chat_bridge_v5_base as precise_runtime
import operator_assist as top_runtime
from operator_assist_runtime import base_runtime


class ModelLoadingPolicyTests(unittest.TestCase):
    def test_chat_settings_persist_selected_precise_model(self):
        app = chat_runtime.OperatorAssistApp.__new__(chat_runtime.OperatorAssistApp)
        app.mic_device_var = SimpleNamespace(get=lambda: "Mic")
        app.speaker_device_var = SimpleNamespace(get=lambda: "Speaker")
        app.chrome_window_var = SimpleNamespace(get=lambda: "ChatGPT")
        app.auto_enter_var = SimpleNamespace(get=lambda: False)
        app._current_capture_mode_key = lambda: "capture_speaker_only"
        app._current_speaker_mode_key = lambda: base_runtime.SPEAKER_MODE_PRECISE
        app._current_precise_device_key = lambda: "gpu"
        app._current_precise_model_key = lambda: base_runtime.PRECISE_MODEL_FAST
        app._operator_prompt_value = lambda: ""
        app._refresh_startup_readiness = lambda: None

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "operator_assist_settings.json"
            with mock.patch.object(chat_runtime._base, "SETTINGS_PATH", settings_path):
                app._save_settings()

            saved = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(base_runtime.PRECISE_MODEL_FAST, saved["precise_model"])

    def test_top_wrapper_builds_precise_model_selector(self):
        build_ui_source = inspect.getsource(top_runtime.OperatorAssistApp._build_ui)

        self.assertIn("self.precise_model_combo =", build_ui_source)
        self.assertIn("textvariable=self.precise_model_var", build_ui_source)
        self.assertIn("self._on_precise_model_selected", build_ui_source)

    def test_top_wrapper_applies_saved_precise_model_before_speaker_mode(self):
        method_names = []
        app = top_runtime.OperatorAssistApp.__new__(top_runtime.OperatorAssistApp)

        class FakeCombo(dict):
            pass

        app.mic_devices = [{"name": "Mic"}]
        app.speaker_sources = [{"label": "Speaker"}]
        app.mic_combo = FakeCombo()
        app.speaker_combo = FakeCombo()
        app.capture_mode_combo = FakeCombo()
        app.speaker_mode_combo = FakeCombo()
        app.precise_device_combo = FakeCombo()
        app.precise_model_combo = FakeCombo()
        app.settings = {
            "mic_device": "Mic",
            "speaker_device": "Speaker",
            "precise_model": base_runtime.PRECISE_MODEL_FAST,
        }
        app.default_loopback_label = None
        app._device_label = lambda device: device["name"]
        app._capture_mode_labels = lambda: []
        app._speaker_mode_labels = lambda: []
        app._precise_device_labels = lambda: []
        app._apply_default_capture_mode = lambda: method_names.append("capture")
        app._apply_default_precise_device = lambda: method_names.append("device")
        app._apply_default_precise_model = lambda: method_names.append("model")
        app._apply_default_speaker_mode = lambda: method_names.append("speaker")
        app._set_audio_controls_running_state = lambda _running: None
        app._find_mic_label = lambda _keywords: "Mic"
        app._find_speaker_label = lambda: "Speaker"
        app._current_capture_mode_key = lambda: "capture"
        app._current_speaker_mode_key = lambda: "speaker"
        app._current_precise_device_key = lambda: "gpu"
        app._current_precise_model_key = lambda: base_runtime.PRECISE_MODEL_FAST
        app._refresh_audio_diagnostics = lambda: None
        app.mic_device_var = SimpleNamespace(set=lambda _value: None, get=lambda: "Mic")
        app.speaker_device_var = SimpleNamespace(set=lambda _value: None, get=lambda: "Speaker")

        app._apply_default_devices()

        self.assertEqual(["capture", "device", "model", "speaker"], method_names)
        self.assertEqual(
            [label for _key, label in base_runtime.PRECISE_MODEL_CHOICES],
            app.precise_model_combo["values"],
        )

    def test_precise_model_labels_round_trip_and_keep_quality_default(self):
        for key, label in base_runtime.PRECISE_MODEL_CHOICES:
            self.assertEqual(key, base_runtime.precise_model_key_from_label(label))
            self.assertEqual(label, base_runtime.precise_model_label(key))

        self.assertEqual(
            base_runtime.PRECISE_MODEL_ACCURATE,
            base_runtime.precise_model_key_from_label("unknown"),
        )

    def test_precise_model_hints_explain_the_measured_tradeoff(self):
        accurate_hint = base_runtime.precise_model_hint(base_runtime.PRECISE_MODEL_ACCURATE)
        fast_hint = base_runtime.precise_model_hint(base_runtime.PRECISE_MODEL_FAST)

        self.assertIn("точнее", accurate_hint)
        self.assertIn("дольше", accurate_hint)
        self.assertIn("быстрее", fast_hint)
        self.assertIn("чаще ошибается", fast_hint)

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

    def test_precise_only_route_reports_whisper_model(self):
        app = precise_runtime.OperatorAssistApp.__new__(precise_runtime.OperatorAssistApp)
        app._capture_mic_enabled = lambda: False
        app._capture_speaker_enabled = lambda: True
        app._current_speaker_mode_key = lambda: base_runtime.SPEAKER_MODE_PRECISE
        app.active_model_dir = None
        app.precise_engine_bundle = SimpleNamespace(
            model_name="large-v3",
            device="cuda",
            compute_type="int8",
        )

        self.assertEqual(
            app._recognition_model_name(),
            "Whisper large-v3 (cuda/int8)",
        )

    def test_mixed_route_reports_vosk_and_whisper_models(self):
        app = precise_runtime.OperatorAssistApp.__new__(precise_runtime.OperatorAssistApp)
        app._capture_mic_enabled = lambda: True
        app._capture_speaker_enabled = lambda: True
        app._current_speaker_mode_key = lambda: base_runtime.SPEAKER_MODE_PRECISE
        app.active_model_dir = SimpleNamespace(name="vosk-model-ru-0.42")
        app.precise_engine_bundle = SimpleNamespace(
            model_name="large-v3",
            device="cuda",
            compute_type="int8",
        )

        self.assertEqual(
            app._recognition_model_name(),
            "Vosk vosk-model-ru-0.42 + Whisper large-v3 (cuda/int8)",
        )


if __name__ == "__main__":
    unittest.main()
