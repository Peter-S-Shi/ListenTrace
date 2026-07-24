from __future__ import annotations

"""Pure, framework-free privacy rules for Milestone 9 (Structured Export).

Two independent kinds of selection exist and must never be confused:

- **Evidence categories** (`EVIDENCE_CATEGORIES`) decide *which kinds of
  records* appear in an export at all (e.g. "include quiz attempts?").
- **Privacy fields** (`PRIVACY_FIELDS`) decide whether a specific
  *potentially sensitive value* is shown or redacted *within* whichever
  categories were included (e.g. "show the raw mishearing text, or redact
  it?"). Turning a privacy field off never removes the surrounding record —
  it only replaces that one field's value with `REDACTED_PLACEHOLDER`.

A third set (`ALWAYS_EXCLUDED_DESCRIPTION`) is not a toggle at all: absolute
local paths, original media/subtitle/recording paths, and anything
resembling a credential or secret are never exported, regardless of any
selection — the exporter code simply never reads those fields into the
export tree in the first place (see `application/services/export_service.py`).
"""

# ---- evidence categories ----

CATEGORY_MATERIAL_METADATA = "material_metadata"
CATEGORY_SESSION_SUMMARIES = "session_summaries"
CATEGORY_STAGE_RESPONSES = "stage_responses"
CATEGORY_SESSION_DIAGNOSIS_HISTORY = "session_diagnosis_history"
CATEGORY_CURRENT_ANNOTATIONS = "current_material_annotations"
CATEGORY_QUIZ_ATTEMPTS = "quiz_attempts"
CATEGORY_QUIZ_QUESTIONS_AND_ANSWERS = "quiz_questions_and_answers"
CATEGORY_SHADOWING_EVIDENCE = "shadowing_evidence"
CATEGORY_RETAINED_RECORDING_METADATA = "retained_recording_metadata"
CATEGORY_LEARNER_NOTES = "learner_notes_and_summaries"
CATEGORY_VOCABULARY = "vocabulary_and_saved_chunks"

# Ordered for stable UI presentation.
EVIDENCE_CATEGORIES: tuple[str, ...] = (
    CATEGORY_MATERIAL_METADATA,
    CATEGORY_SESSION_SUMMARIES,
    CATEGORY_STAGE_RESPONSES,
    CATEGORY_SESSION_DIAGNOSIS_HISTORY,
    CATEGORY_CURRENT_ANNOTATIONS,
    CATEGORY_QUIZ_ATTEMPTS,
    CATEGORY_QUIZ_QUESTIONS_AND_ANSWERS,
    CATEGORY_SHADOWING_EVIDENCE,
    CATEGORY_RETAINED_RECORDING_METADATA,
    CATEGORY_LEARNER_NOTES,
    CATEGORY_VOCABULARY,
)

# "Defaults should be useful without oversharing": the aggregate/summary
# categories a learner would normally want an external evaluator to see are
# on by default; the two most verbose, raw-text-heavy categories (the literal
# text of every Stage 1/2/5 response, and every quiz question's full prompt/
# answer text) are off by default — a learner opts into the raw transcript-
# adjacent detail deliberately rather than getting it by default.
DEFAULT_CATEGORIES: frozenset[str] = frozenset(
    {
        CATEGORY_MATERIAL_METADATA,
        CATEGORY_SESSION_SUMMARIES,
        CATEGORY_SESSION_DIAGNOSIS_HISTORY,
        CATEGORY_CURRENT_ANNOTATIONS,
        CATEGORY_QUIZ_ATTEMPTS,
        CATEGORY_SHADOWING_EVIDENCE,
        CATEGORY_RETAINED_RECORDING_METADATA,
        CATEGORY_LEARNER_NOTES,
        CATEGORY_VOCABULARY,
    }
)

# ---- privacy-controlled fields ----

PRIVACY_TRANSCRIPT_EXCERPTS = "transcript_excerpts"
PRIVACY_LEARNER_NOTES = "learner_notes"
PRIVACY_MISHEARING_TEXT = "mishearing_text"
PRIVACY_VOCABULARY_MEANINGS = "vocabulary_meanings"
PRIVACY_SOURCE_LABELS = "source_labels"
PRIVACY_LOCAL_FILE_NAMES = "local_file_names"

PRIVACY_FIELDS: tuple[str, ...] = (
    PRIVACY_TRANSCRIPT_EXCERPTS,
    PRIVACY_LEARNER_NOTES,
    PRIVACY_MISHEARING_TEXT,
    PRIVACY_VOCABULARY_MEANINGS,
    PRIVACY_SOURCE_LABELS,
    PRIVACY_LOCAL_FILE_NAMES,
)

# A privacy field being present in this set means its value is INCLUDED
# (shown); absent means REDACTED. `local_file_names` is the one field off by
# default — a bare filename (never a full path, which is always excluded
# regardless of any selection) can still be personally identifying in a way
# the other fields typically are not.
DEFAULT_PRIVACY_FIELDS: frozenset[str] = frozenset(
    {
        PRIVACY_TRANSCRIPT_EXCERPTS,
        PRIVACY_LEARNER_NOTES,
        PRIVACY_MISHEARING_TEXT,
        PRIVACY_VOCABULARY_MEANINGS,
        PRIVACY_SOURCE_LABELS,
    }
)

REDACTED_PLACEHOLDER = "[redacted]"

# Documents the hard boundary (see module docstring) — not a runtime toggle
# read anywhere; this exists so the boundary is written down once, in code,
# next to the rest of the privacy rules, rather than only in prose docs.
ALWAYS_EXCLUDED_DESCRIPTION: tuple[str, ...] = (
    "absolute local media paths",
    "absolute local subtitle paths",
    "absolute local recording paths",
    "application-data directory paths",
    "credentials or secrets",
)


def is_category_included(categories: frozenset[str], category: str) -> bool:
    return category in categories


def redact_unless_included(value: str | None, field: str, privacy_fields: frozenset[str]) -> str | None:
    """Returns `value` unchanged if `field` is in `privacy_fields`
    (included), else `REDACTED_PLACEHOLDER` — never `None` silently standing
    in for "redacted" (which would be indistinguishable from "no value was
    ever recorded")."""
    if value is None:
        return None
    return value if field in privacy_fields else REDACTED_PLACEHOLDER


def sanitize_filename_for_label(path: str) -> str:
    """The bare filename only (no directory component) — used exclusively
    when `PRIVACY_LOCAL_FILE_NAMES` is included. Never returns a path
    separator or a drive/UNC prefix."""
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]
