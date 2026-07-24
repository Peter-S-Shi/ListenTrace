from __future__ import annotations

import re

from listentrace.domain.enums.annotation_label import AnnotationLabel
from listentrace.domain.enums.quiz_status import QuizStatus

# Pure, framework-free quiz generation/scoring rules. No sqlite, no Qt: the
# application layer loads whatever data these functions need (cues, existing
# annotations, saved items, keyword captures) and supplies a seeded
# `random.Random` so every decision here stays deterministic and reproducible.

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"\S+", re.UNICODE)

# Diagnosis-evidence label priority for Review Quiz generation, highest first.
REVIEW_LABEL_PRIORITY: tuple[str, ...] = (
    AnnotationLabel.MISHEARD.value,
    AnnotationLabel.KNOWN_NOT_HEARD.value,
    AnnotationLabel.UNKNOWN_WORD_OR_CHUNK.value,
    AnnotationLabel.CONNECTED_REDUCED_SPEECH.value,
)

# Audio-to-transcript-choice needs at least this many valid distractors (i.e.
# at least a 3-way choice) to be worth asking; weaker candidates are skipped
# rather than forced into a near-trivial 2-option question.
MIN_TRANSCRIPT_CHOICE_DISTRACTORS = 2
MAX_TRANSCRIPT_CHOICE_DISTRACTORS = 3

_QUIZ_TRANSITIONS: dict[str, frozenset[str]] = {
    QuizStatus.ACTIVE.value: frozenset({QuizStatus.COMPLETED.value, QuizStatus.ABANDONED.value}),
}


def is_valid_quiz_transition(current_status: str, new_status: str) -> bool:
    return new_status in _QUIZ_TRANSITIONS.get(current_status, frozenset())


def normalize_answer_text(text: str) -> str:
    """Case-, punctuation-, and whitespace-insensitive normalization used for all
    dictation/fill-in/review-missed scoring: strip leading/trailing whitespace,
    collapse internal whitespace, drop punctuation, fold case. Spelling must
    otherwise match exactly — no fuzzy or semantic matching."""
    without_punctuation = _PUNCTUATION_RE.sub("", text)
    collapsed = _WHITESPACE_RE.sub(" ", without_punctuation).strip()
    return collapsed.casefold()


def is_text_answer_correct(raw_answer: str, correct_normalized_text: str) -> bool:
    return normalize_answer_text(raw_answer) == correct_normalized_text


def tokenize_cue(text: str) -> list[tuple[str, int, int]]:
    """Whitespace-delimited tokens with their zero-based, end-exclusive codepoint
    offsets into `text` (the same offset convention as `text_range.py`)."""
    return [(match.group(0), match.start(), match.end()) for match in _TOKEN_RE.finditer(text)]


def meaningful_tokens(text: str) -> list[tuple[str, int, int]]:
    """Tokens that carry at least one word character once normalized — excludes
    punctuation-only or whitespace-only tokens, which can never be scored
    reliably as a dictation answer."""
    return [(tok, start, end) for tok, start, end in tokenize_cue(text) if normalize_answer_text(tok)]


def is_cue_usable_for_quiz(cue_text: str) -> bool:
    """A cue can support at least a full-cue dictation question only if it has
    some real (non-punctuation, non-whitespace) content."""
    return len(meaningful_tokens(cue_text)) > 0


def select_blank_span(text: str, rng) -> tuple[str, int, int] | None:
    """Pick one meaningful token to blank out, deterministically via `rng`.

    Returns None (meaning: fall back to full-cue dictation) when there are
    fewer than two meaningful tokens — blanking a cue's only meaningful token
    would leave no useful context to answer from.
    """
    tokens = meaningful_tokens(text)
    if len(tokens) < 2:
        return None
    return rng.choice(tokens)


def build_masked_text(text: str, blank_start: int, blank_end: int, marker: str = "____") -> str:
    return text[:blank_start] + marker + text[blank_end:]


def cue_contains_target(cue_text: str, target_text: str) -> bool:
    """Whole-token(s) containment check: does `target_text` occur in `cue_text`
    as one or more contiguous, normalized-boundary tokens? Avoids ambiguous
    substring matches (e.g. "cat" must not match inside "category")."""
    target_tokens = [normalize_answer_text(tok) for tok, _, _ in meaningful_tokens(target_text)]
    target_tokens = [tok for tok in target_tokens if tok]
    if not target_tokens:
        return False
    cue_tokens = [normalize_answer_text(tok) for tok, _, _ in meaningful_tokens(cue_text)]
    span = len(target_tokens)
    for i in range(len(cue_tokens) - span + 1):
        if cue_tokens[i : i + span] == target_tokens:
            return True
    return False


def build_distinct_distractors(correct_text: str, candidate_texts: list[str], max_count: int) -> list[str]:
    """Dedupe candidates against the correct answer and each other by normalized
    text, dropping near-empty candidates, and cap at `max_count`. Order of
    `candidate_texts` is the caller's (already seeded/shuffled) selection order."""
    seen = {normalize_answer_text(correct_text)}
    chosen: list[str] = []
    for text in candidate_texts:
        normalized = normalize_answer_text(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        chosen.append(text)
        if len(chosen) >= max_count:
            break
    return chosen
