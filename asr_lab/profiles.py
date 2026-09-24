"""One-variable experiments plus explicit legacy and production controls."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    engine_kind: str = "buffered"
    flush_seconds: float = 6.0
    min_segment_seconds: float = 0.7
    context_source: str = "corrected"
    beam_size: int = 5
    vad_silence_ms: int = 350
    preprocessing: bool = True
    use_hotwords: bool = False
    pause_flush_seconds: float = 12.0
    pause_initial_flush_seconds: float = 4.0
    pause_overlap_seconds: float = 1.0
    pause_boundary_guard_seconds: float = 0.6
    pause_ms: int = 450
    pause_short_pause_ms: int = 750
    pause_min_window_seconds: float = 1.5
    pause_beam_size: int = 5
    pause_best_of: int = 5
    pause_preview_enabled: bool = True
    pause_preview_after_seconds: float = 1.5
    pause_decode_tail_seconds: float = 0.35


PROFILES = {
    profile.name: profile for profile in (
        Profile("baseline"),
        Profile("production_pause", engine_kind="pause", preprocessing=False),
        Profile(
            "pause_legacy",
            engine_kind="pause",
            preprocessing=False,
            pause_ms=600,
            pause_short_pause_ms=1000,
            pause_min_window_seconds=2.5,
            pause_beam_size=8,
            pause_preview_after_seconds=2.5,
        ),
        Profile(
            "pause_preview_off",
            engine_kind="pause",
            preprocessing=False,
            pause_preview_enabled=False,
        ),
        Profile(
            "pause_initial_6",
            engine_kind="pause",
            preprocessing=False,
            pause_initial_flush_seconds=6.0,
        ),
        Profile(
            "pause_initial_8",
            engine_kind="pause",
            preprocessing=False,
            pause_initial_flush_seconds=8.0,
        ),
        Profile(
            "pause_flush_16",
            engine_kind="pause",
            preprocessing=False,
            pause_flush_seconds=16.0,
        ),
        Profile(
            "pause_overlap_1_5",
            engine_kind="pause",
            preprocessing=False,
            pause_overlap_seconds=1.5,
        ),
        Profile(
            "pause_guard_0_9",
            engine_kind="pause",
            preprocessing=False,
            pause_boundary_guard_seconds=0.9,
        ),
        Profile(
            "pause_ms_450",
            engine_kind="pause",
            preprocessing=False,
            pause_ms=450,
        ),
        Profile(
            "pause_preview_1_5",
            engine_kind="pause",
            preprocessing=False,
            pause_preview_after_seconds=1.5,
        ),
        Profile(
            "pause_short_750",
            engine_kind="pause",
            preprocessing=False,
            pause_ms=450,
            pause_short_pause_ms=750,
            pause_min_window_seconds=1.5,
        ),
        Profile(
            "latency_balanced",
            engine_kind="pause",
            preprocessing=False,
            pause_ms=450,
            pause_short_pause_ms=750,
            pause_min_window_seconds=1.5,
            pause_beam_size=5,
            pause_preview_after_seconds=1.5,
        ),
        Profile(
            "pause_beam_5",
            engine_kind="pause",
            preprocessing=False,
            pause_beam_size=5,
        ),
        Profile(
            "pause_beam_10",
            engine_kind="pause",
            preprocessing=False,
            pause_beam_size=10,
        ),
        Profile("context_off", context_source="none"),
        Profile("raw_context", context_source="raw"),
        Profile("term_hints", use_hotwords=True),
        Profile("preserve_short", min_segment_seconds=0.2),
        Profile("longer_chunks", flush_seconds=8.0),
        Profile("vad_700ms", vad_silence_ms=700),
        Profile("beam_3", beam_size=3),
        Profile("audio_bypass", preprocessing=False),
    )
}
