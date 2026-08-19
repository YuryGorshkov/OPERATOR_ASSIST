"""Pure audio-diagnostic helpers for OPERATOR_ASSIST."""

SIGNAL_LIVE_THRESHOLD = 8
NO_SIGNAL_GRACE_SEC = 3.0


def describe_signal_state(level_percent):
    """Map the raw level percentage to a user-facing state label."""
    if level_percent >= 60:
        return "сильный"
    if level_percent >= 25:
        return "есть"
    if level_percent >= SIGNAL_LIVE_THRESHOLD:
        return "слабый"
    return "тишина"


def build_route_diagnostic_message(
    *,
    workers_active,
    mic_mode_label,
    speaker_mode_label,
    mic_selected,
    speaker_selected,
    mic_has_live_signal=False,
    speaker_has_live_signal=False,
    seconds_since_start=0.0,
    no_signal_grace_sec=NO_SIGNAL_GRACE_SEC,
):
    """Build a practical human-readable routing and signal hint."""
    mic_mode_label = (mic_mode_label or "вход").strip() or "вход"
    speaker_mode_label = (speaker_mode_label or "вход").strip() or "вход"

    if not mic_selected and not speaker_selected:
        return "Диагностика: выберите микрофон оператора и источник собеседника, затем запустите распознавание."
    if not mic_selected:
        return "Диагностика: выберите микрофон оператора, иначе левое окно будет пустым."
    if not speaker_selected:
        return "Диагностика: выберите источник собеседника или системного звука, иначе правое окно будет пустым."

    if not workers_active:
        return (
            "Маршрут выбран: "
            f"оператор -> {mic_mode_label}; "
            f"собеседник -> {speaker_mode_label}. "
            "После старта следите за уровнями сигнала ниже."
        )

    if seconds_since_start >= no_signal_grace_sec:
        if not mic_has_live_signal and not speaker_has_live_signal:
            return (
                "Диагностика: после старта оба канала пока без живого сигнала. "
                "Проверьте mute гарнитуры, разрешение микрофона и выбранный источник собеседника."
            )
        if not mic_has_live_signal:
            return (
                "Диагностика: микрофон оператора пока без живого сигнала. "
                "Проверьте mute гарнитуры, выбранный микрофон и уровень записи Windows."
            )
        if not speaker_has_live_signal:
            return (
                "Диагностика: канал собеседника пока без живого сигнала. "
                "Проверьте WASAPI loopback или запасной источник вроде Stereo Mix."
            )

    if mic_has_live_signal and speaker_has_live_signal:
        return (
            "Диагностика: оба канала уже дают живой сигнал. "
            "Если тексты дублируются, проверьте маршрутизацию и не попадает ли микрофон в канал собеседника."
        )

    if mic_has_live_signal or speaker_has_live_signal:
        return (
            "Диагностика: один канал уже живой, второй еще проверяется. "
            "Скажите короткую тестовую фразу и убедитесь, что уровни шевелятся отдельно."
        )

    return (
        "Маршрут активен: "
        f"оператор -> {mic_mode_label}; "
        f"собеседник -> {speaker_mode_label}. "
        "Если через несколько секунд уровни не появятся, проверьте выбор источников."
    )
