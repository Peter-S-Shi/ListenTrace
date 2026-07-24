from __future__ import annotations

import random

from listentrace.domain.services import quiz_rules as rules


def test_normalize_answer_text_ignores_case_punctuation_and_whitespace():
    assert rules.normalize_answer_text("  Bonjour,   le Monde!  ") == "bonjour le monde"
    assert rules.normalize_answer_text("bonjour le monde") == "bonjour le monde"


def test_normalize_answer_text_requires_exact_spelling_otherwise():
    assert rules.normalize_answer_text("bonjour") != rules.normalize_answer_text("bonjoure")


def test_is_text_answer_correct_uses_normalized_comparison():
    correct = rules.normalize_answer_text("Bonjour, le monde!")
    assert rules.is_text_answer_correct("  bonjour   LE MONDE  ", correct)
    assert not rules.is_text_answer_correct("bonjour le mond", correct)


def test_tokenize_cue_returns_offsets_that_round_trip():
    text = "Bonjour le monde"
    tokens = rules.tokenize_cue(text)
    assert [tok for tok, _, _ in tokens] == ["Bonjour", "le", "monde"]
    for tok, start, end in tokens:
        assert text[start:end] == tok


def test_meaningful_tokens_excludes_punctuation_only_tokens():
    text = "Bonjour ... le monde !!"
    meaningful = [tok for tok, _, _ in rules.meaningful_tokens(text)]
    assert meaningful == ["Bonjour", "le", "monde"]


def test_is_cue_usable_for_quiz():
    assert rules.is_cue_usable_for_quiz("Bonjour le monde")
    assert not rules.is_cue_usable_for_quiz("... !!!")
    assert not rules.is_cue_usable_for_quiz("   ")


def test_select_blank_span_returns_none_for_a_single_meaningful_token():
    assert rules.select_blank_span("Bonjour", random.Random(1)) is None
    assert rules.select_blank_span("Bonjour !!!", random.Random(1)) is None


def test_select_blank_span_is_deterministic_for_a_given_seed():
    text = "Bonjour le monde entier"
    first = rules.select_blank_span(text, random.Random(42))
    second = rules.select_blank_span(text, random.Random(42))
    assert first == second
    assert first is not None
    token, start, end = first
    assert text[start:end] == token


def test_build_masked_text_replaces_exactly_the_given_span():
    text = "Bonjour le monde"
    masked = rules.build_masked_text(text, 8, 10, marker="____")
    assert masked == "Bonjour ____ monde"


def test_cue_contains_target_matches_whole_token_boundaries_only():
    cue = "The category is broad"
    assert rules.cue_contains_target(cue, "category")
    assert not rules.cue_contains_target(cue, "cat")


def test_cue_contains_target_matches_multi_word_chunks_contiguously():
    cue = "I will see you later today"
    assert rules.cue_contains_target(cue, "see you later")
    assert not rules.cue_contains_target(cue, "you later see")


def test_cue_contains_target_is_case_and_punctuation_insensitive():
    cue = "Bonjour, le monde!"
    assert rules.cue_contains_target(cue, "LE MONDE")


def test_cue_contains_target_rejects_empty_or_punctuation_only_target():
    assert not rules.cue_contains_target("Bonjour le monde", "...")
    assert not rules.cue_contains_target("Bonjour le monde", "")


def test_build_distinct_distractors_excludes_correct_answer_and_duplicates():
    correct = "Bonjour le monde"
    candidates = ["Bonjour LE MONDE!", "Comment ça va", "comment ça va", "Au revoir", ""]
    distractors = rules.build_distinct_distractors(correct, candidates, max_count=3)
    assert distractors == ["Comment ça va", "Au revoir"]


def test_build_distinct_distractors_respects_max_count():
    correct = "x"
    candidates = ["a", "b", "c", "d"]
    distractors = rules.build_distinct_distractors(correct, candidates, max_count=2)
    assert len(distractors) == 2
    assert distractors == ["a", "b"]


def test_is_valid_quiz_transition_only_allows_active_to_terminal():
    assert rules.is_valid_quiz_transition("active", "completed")
    assert rules.is_valid_quiz_transition("active", "abandoned")
    assert not rules.is_valid_quiz_transition("completed", "active")
    assert not rules.is_valid_quiz_transition("abandoned", "completed")
    assert not rules.is_valid_quiz_transition("completed", "abandoned")
