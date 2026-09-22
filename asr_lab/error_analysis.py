"""Transparent word-level error candidates for human dictionary review."""

from collections import Counter, defaultdict

from .metrics import edit_counts, tokens


def align_words(reference, hypothesis):
    expected = tokens(reference)
    actual = tokens(hypothesis)
    rows = [[None] * (len(actual) + 1) for _ in range(len(expected) + 1)]
    rows[0][0] = (0, 0, ())
    for left in range(1, len(expected) + 1):
        rows[left][0] = (
            left,
            rows[left - 1][0][1] + len(expected[left - 1]),
            rows[left - 1][0][2] + (("deletion", expected[left - 1], ""),),
        )
    for right in range(1, len(actual) + 1):
        rows[0][right] = (
            right,
            rows[0][right - 1][1] + len(actual[right - 1]),
            rows[0][right - 1][2] + (("insertion", "", actual[right - 1]),),
        )

    for left in range(1, len(expected) + 1):
        for right in range(1, len(actual) + 1):
            if expected[left - 1] == actual[right - 1]:
                cost, character_cost, path = rows[left - 1][right - 1]
                rows[left][right] = (
                    cost,
                    character_cost,
                    path + (("equal", expected[left - 1], actual[right - 1]),),
                )
                continue
            substitution = (
                rows[left - 1][right - 1][0] + 1,
                rows[left - 1][right - 1][1]
                + edit_counts(expected[left - 1], actual[right - 1]).errors,
                rows[left - 1][right - 1][2]
                + (("substitution", expected[left - 1], actual[right - 1]),),
            )
            deletion = (
                rows[left - 1][right][0] + 1,
                rows[left - 1][right][1] + len(expected[left - 1]),
                rows[left - 1][right][2]
                + (("deletion", expected[left - 1], ""),),
            )
            insertion = (
                rows[left][right - 1][0] + 1,
                rows[left][right - 1][1] + len(actual[right - 1]),
                rows[left][right - 1][2]
                + (("insertion", "", actual[right - 1]),),
            )
            rows[left][right] = min(
                (substitution, deletion, insertion), key=lambda item: item[:2]
            )
    return list(rows[-1][-1][2])


def collect_error_candidates(results):
    counts = Counter()
    sample_ids = defaultdict(set)
    speaker_ids = defaultdict(set)
    for result in results:
        if "error" in result:
            continue
        for operation, expected, observed in align_words(
            result["reference"], result["hypothesis"]
        ):
            if operation == "equal":
                continue
            key = (operation, expected, observed)
            counts[key] += 1
            sample_ids[key].add(result["id"])
            speaker_ids[key].add(result["speaker_id"])

    candidates = []
    for key, occurrences in counts.most_common():
        operation, expected, observed = key
        speakers = sorted(speaker_ids[key])
        repeated_across_voices = occurrences >= 2 and len(speakers) >= 2
        candidate = {
            "operation": operation,
            "expected": expected,
            "observed": observed,
            "occurrences": occurrences,
            "sample_ids": sorted(sample_ids[key]),
            "speaker_ids": speakers,
            "review_priority": "high" if repeated_across_voices else "normal",
            "auto_apply": False,
        }
        if operation == "substitution":
            candidate["candidate_replacement"] = {
                "from": observed,
                "to": expected,
            }
        candidates.append(candidate)
    return candidates
