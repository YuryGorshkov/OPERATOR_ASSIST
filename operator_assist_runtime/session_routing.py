"""Pure helpers for capture-mode and audio-source routing decisions."""

CAPTURE_MODE_BOTH = "capture_both"
CAPTURE_MODE_SPEAKER_ONLY = "capture_speaker_only"
CAPTURE_MODE_MIC_ONLY = "capture_mic_only"

CAPTURE_MODE_CHOICES = (
    (CAPTURE_MODE_BOTH, "Оба канала"),
    (CAPTURE_MODE_SPEAKER_ONLY, "Только собеседник"),
    (CAPTURE_MODE_MIC_ONLY, "Только оператор"),
)


def capture_mode_label(mode_key):
    for key, label in CAPTURE_MODE_CHOICES:
        if key == mode_key:
            return label
    return CAPTURE_MODE_CHOICES[0][1]


def capture_mode_key_from_label(label):
    for key, mode_label in CAPTURE_MODE_CHOICES:
        if mode_label == label:
            return key
    return CAPTURE_MODE_BOTH


def capture_mode_uses_mic(mode_key):
    return mode_key in (CAPTURE_MODE_BOTH, CAPTURE_MODE_MIC_ONLY)


def capture_mode_uses_speaker(mode_key):
    return mode_key in (CAPTURE_MODE_BOTH, CAPTURE_MODE_SPEAKER_ONLY)


def select_best_signal_source(results, *, minimum_level=8):
    """Return the strongest successful probe result, or None for silence."""

    usable = [
        result
        for result in results
        if not result.get("error") and int(result.get("level_percent") or 0) >= minimum_level
    ]
    if not usable:
        return None
    return max(usable, key=lambda result: int(result.get("level_percent") or 0))
