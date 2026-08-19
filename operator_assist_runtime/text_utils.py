"""Shared text normalization helpers for OPERATOR_ASSIST."""

from difflib import SequenceMatcher


def normalize_name(value):
    return " ".join((value or "").strip().casefold().split())


def short_text(value, limit=220):
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def are_exact_duplicates(left, right, *, min_chars=12):
    left_norm = normalize_name(left)
    right_norm = normalize_name(right)

    if not left_norm or not right_norm:
        return False

    if len(left_norm) < min_chars or len(right_norm) < min_chars:
        return False

    return left_norm == right_norm


def are_similar_duplicates(
    left,
    right,
    *,
    min_chars=16,
    ratio=0.84,
    min_shared_tokens=3,
    shared_token_ratio=0.6,
):
    left_norm = normalize_name(left)
    right_norm = normalize_name(right)

    if not left_norm or not right_norm:
        return False

    if len(left_norm) < min_chars or len(right_norm) < min_chars:
        return False

    if left_norm == right_norm:
        return True

    shorter_len = min(len(left_norm), len(right_norm))
    longer_len = max(len(left_norm), len(right_norm))
    if shorter_len / longer_len >= 0.72 and (
        left_norm in right_norm or right_norm in left_norm
    ):
        return True

    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    shared_tokens = left_tokens & right_tokens
    if shared_tokens and len(shared_tokens) >= min_shared_tokens:
        shorter_token_count = min(len(left_tokens), len(right_tokens))
        if shorter_token_count and (
            len(shared_tokens) / float(shorter_token_count)
        ) >= shared_token_ratio:
            return True

    return SequenceMatcher(None, left_norm, right_norm).ratio() >= ratio
