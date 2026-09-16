"""Deterministic corpus-level metrics, with no phonetic autocorrections."""

from dataclasses import asdict, dataclass
import re
import unicodedata


def tokens(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("\u0451", "\u0435")
    return re.findall(r"[^\W_]+(?:[+#]+)?", text, flags=re.UNICODE)


@dataclass(frozen=True)
class EditCounts:
    reference: int
    substitutions: int
    deletions: int
    insertions: int

    @property
    def errors(self):
        return self.substitutions + self.deletions + self.insertions

    @property
    def rate(self):
        return self.errors / self.reference if self.reference else None

    def payload(self):
        return {**asdict(self), "errors": self.errors, "rate": self.rate}


def edit_counts(reference, hypothesis):
    # Keep operation counts in the DP rows so substitutions are not guessed later.
    previous = [(j, 0, 0, j) for j in range(len(hypothesis) + 1)]
    for i, expected in enumerate(reference, 1):
        current = [(i, 0, i, 0)]
        for j, actual in enumerate(hypothesis, 1):
            if expected == actual:
                current.append(previous[j - 1])
                continue
            cost, sub, delete, insert = previous[j - 1]
            substitution = (cost + 1, sub + 1, delete, insert)
            cost, sub, delete, insert = previous[j]
            deletion = (cost + 1, sub, delete + 1, insert)
            cost, sub, delete, insert = current[j - 1]
            insertion = (cost + 1, sub, delete, insert + 1)
            current.append(min((substitution, deletion, insertion), key=lambda item: item[0]))
        previous = current
    _, sub, delete, insert = previous[-1]
    return EditCounts(len(reference), sub, delete, insert)


def score_text(reference, hypothesis):
    expected, actual = tokens(reference), tokens(hypothesis)
    return {
        "wer": edit_counts(expected, actual).payload(),
        "cer": edit_counts(list(" ".join(expected)), list(" ".join(actual))).payload(),
    }


def aggregate(scores, key):
    fields = ("reference", "substitutions", "deletions", "insertions")
    totals = {field: sum(score[key][field] for score in scores) for field in fields}
    return EditCounts(**totals).payload()


def phrase_count(text, phrase):
    words, target = tokens(text), tokens(phrase)
    if not target:
        return 0
    return sum(words[i:i + len(target)] == target for i in range(len(words) - len(target) + 1))


def score_terms(reference, hypothesis, terms):
    result = []
    for term in terms:
        expected = phrase_count(reference, term)
        actual = phrase_count(hypothesis, term)
        result.append({
            "term": term, "expected": expected, "recognized": min(expected, actual),
            "extra": max(0, actual - expected),
        })
    return result
