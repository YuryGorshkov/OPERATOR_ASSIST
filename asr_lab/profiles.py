"""One-variable experiments; baseline always preserves desktop behavior."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    flush_seconds: float = 6.0
    min_segment_seconds: float = 0.7
    context_source: str = "corrected"
    beam_size: int = 5
    vad_silence_ms: int = 350
    preprocessing: bool = True
    use_hotwords: bool = False


PROFILES = {
    profile.name: profile for profile in (
        Profile("baseline"),
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
