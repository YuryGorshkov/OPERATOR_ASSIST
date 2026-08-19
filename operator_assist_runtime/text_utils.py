"""Shared text normalization helpers for OPERATOR_ASSIST."""


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
