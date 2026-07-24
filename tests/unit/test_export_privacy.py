from __future__ import annotations

from listentrace.domain.services import export_privacy as rules


def test_default_categories_are_a_subset_of_all_categories():
    assert rules.DEFAULT_CATEGORIES <= set(rules.EVIDENCE_CATEGORIES)


def test_default_categories_exclude_the_two_most_verbose_raw_text_categories():
    assert rules.CATEGORY_STAGE_RESPONSES not in rules.DEFAULT_CATEGORIES
    assert rules.CATEGORY_QUIZ_QUESTIONS_AND_ANSWERS not in rules.DEFAULT_CATEGORIES


def test_default_privacy_fields_are_a_subset_of_all_fields():
    assert rules.DEFAULT_PRIVACY_FIELDS <= set(rules.PRIVACY_FIELDS)


def test_local_file_names_is_excluded_by_default():
    assert rules.PRIVACY_LOCAL_FILE_NAMES not in rules.DEFAULT_PRIVACY_FIELDS


def test_redact_unless_included_returns_value_when_field_is_included():
    included = frozenset({rules.PRIVACY_LEARNER_NOTES})
    assert rules.redact_unless_included("a private note", rules.PRIVACY_LEARNER_NOTES, included) == "a private note"


def test_redact_unless_included_redacts_when_field_is_excluded():
    included = frozenset()
    assert rules.redact_unless_included("a private note", rules.PRIVACY_LEARNER_NOTES, included) == rules.REDACTED_PLACEHOLDER


def test_redact_unless_included_never_turns_a_missing_value_into_a_placeholder():
    included = frozenset()
    assert rules.redact_unless_included(None, rules.PRIVACY_LEARNER_NOTES, included) is None


def test_sanitize_filename_for_label_strips_windows_directories():
    assert rules.sanitize_filename_for_label("C:\\Users\\name\\Videos\\lesson.mp4") == "lesson.mp4"


def test_sanitize_filename_for_label_strips_posix_directories():
    assert rules.sanitize_filename_for_label("/home/name/videos/lesson.mp4") == "lesson.mp4"


def test_sanitize_filename_for_label_passes_through_a_bare_filename():
    assert rules.sanitize_filename_for_label("lesson.mp4") == "lesson.mp4"


def test_always_excluded_description_is_non_empty_and_documents_paths_and_secrets():
    joined = " ".join(rules.ALWAYS_EXCLUDED_DESCRIPTION)
    assert "path" in joined
    assert "credential" in joined or "secret" in joined
