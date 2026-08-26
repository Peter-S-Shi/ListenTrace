from __future__ import annotations

import json

from listentrace.application.dto.export import ExportBundle
from listentrace.application.services import export_formatters as fmt


def _bundle(materials=None) -> ExportBundle:
    return ExportBundle(
        export_version=1,
        generated_at="2026-07-24 12:00:00",
        timestamp_convention="UTC, not converted.",
        scope_description="All Materials",
        date_range_description="All Time",
        categories=["material_metadata"],
        privacy_fields=["transcript_excerpts"],
        materials=materials or [],
    )


def test_escape_markdown_line_escapes_inline_special_characters():
    assert fmt.escape_markdown_line("a*b_c[d]e|f`g") == "a\\*b\\_c\\[d\\]e\\|f\\`g"


def test_escape_markdown_line_escapes_leading_structural_characters():
    assert fmt.escape_markdown_line("# heading") == "\\# heading"
    assert fmt.escape_markdown_line("- item") == "\\- item"
    assert fmt.escape_markdown_line("> quote") == "\\> quote"


def test_escape_markdown_line_leaves_ordinary_punctuation_alone():
    assert fmt.escape_markdown_line("It's 3.5 km, co-worker!") == "It's 3.5 km, co-worker!"


def test_escape_markdown_multiline_preserves_line_breaks():
    text = "line one\nline two\n- not a list here"
    escaped = fmt.escape_markdown_multiline(text)
    lines = escaped.split("\n")
    assert lines[0] == "line one"
    assert lines[1] == "line two"
    assert lines[2] == "\\- not a list here"


def test_render_markdown_includes_scope_and_date_range_and_categories():
    md = fmt.render_markdown(_bundle())
    assert "All Materials" in md
    assert "All Time" in md
    assert "material_metadata" in md
    assert "transcript_excerpts" in md


def test_render_markdown_preserves_multiline_stage_responses():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "sessions": [
            {
                "session_id": 1,
                "status": "active",
                "mode": "intensive",
                "stage_responses": [
                    {"stage_key": "global_comprehension", "prompt_key": "who_is_speaking", "response_text": "line one\nline two"}
                ],
                "keyword_captures": [],
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "> line one" in md
    assert "> line two" in md


def test_render_markdown_escapes_special_characters_in_transcript_excerpts():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "session_diagnosis_history": [
            {
                "session_id": 1,
                "subtitle_cue_id": 1,
                "label_key": "misheard",
                "transcript_excerpt": "a * word | here",
                "heard_as": "b_word",
                "created_at": "2026-07-24 12:00:00",
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "a \\* word \\| here" in md
    assert "b\\_word" in md


def test_render_markdown_handles_empty_materials_list():
    md = fmt.render_markdown(_bundle([]))
    assert "no materials matched" in md.lower()


# ---- Quick Practice parity (M14 Human QA Round 2 export-parity corrective) ----


def test_render_markdown_includes_quick_practice_section_with_run_and_item_evidence():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "quick_practice_evidence": [
            {
                "session_id": 7,
                "source_type": "weakest_cues",
                "status": "completed",
                "requested_count": 5,
                "actual_count": 5,
                "started_at": "2026-07-24 12:00:00",
                "completed_at": "2026-07-24 12:05:00",
                "abandoned_at": None,
                "items": [
                    {
                        "position": 1,
                        "subtitle_cue_id": 42,
                        "recall_result": "recalled",
                        "heard_fragment": "gonna",
                        "completed": True,
                        "shadowed": False,
                        "diagnosis": [
                            {
                                "label_key": "connected_speech",
                                "transcript_excerpt": "going to",
                                "heard_as": "gonna",
                                "note": "reduced speech",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "Quick Practice" in md
    assert "Run #7" in md
    assert "weakest" in md and "cues" in md
    assert "gonna" in md
    assert "connected_speech" in md
    assert "reduced speech" in md


def test_render_markdown_quick_practice_empty_run_says_no_items():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "quick_practice_evidence": [
            {
                "session_id": 1,
                "source_type": "recent",
                "status": "abandoned",
                "requested_count": 3,
                "actual_count": 0,
                "started_at": "2026-07-24 12:00:00",
                "completed_at": None,
                "abandoned_at": "2026-07-24 12:01:00",
                "items": [],
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "No items recorded" in md


# ---- Quiz Q&A parity ----


def test_render_markdown_quiz_qa_free_text_includes_learner_and_correct_answer_and_correctness():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "quiz_attempts": [
            {
                "attempt_id": 1,
                "quiz_mode": "dictation",
                "completed_at": "2026-07-24 12:00:00",
                "correct_count": 1,
                "actual_count": 1,
                "accuracy": 1.0,
                "questions": [
                    {
                        "position": 1,
                        "question_type": "dictation",
                        "source_cue_text": "I am going to school",
                        "prompt": {"masked_text": "I am ___ to school"},
                        "correct_answer": {"answer_text": "going"},
                        "learner_answer": {"raw_answer_text": "going", "selected_choice_index": None, "is_correct": True},
                    }
                ],
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "Learner answer" in md
    assert "Correct answer" in md
    assert "going" in md


def test_render_markdown_quiz_qa_choice_question_shows_readable_choice_text():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "quiz_attempts": [
            {
                "attempt_id": 1,
                "quiz_mode": "audio_transcript_choice",
                "completed_at": "2026-07-24 12:00:00",
                "correct_count": 0,
                "actual_count": 1,
                "accuracy": 0.0,
                "questions": [
                    {
                        "position": 1,
                        "question_type": "audio_transcript_choice",
                        "source_cue_text": "She sells seashells",
                        "prompt": {"choices": ["She sells seashells", "She smells seashells"]},
                        "correct_answer": {"correct_choice_index": 0, "correct_text": "She sells seashells"},
                        "learner_answer": {"raw_answer_text": None, "selected_choice_index": 1, "is_correct": False},
                    }
                ],
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "She smells seashells" in md
    assert "She sells seashells" in md


# ---- Diagnosis/annotation note parity ----


def test_render_markdown_session_diagnosis_history_note_survives():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "session_diagnosis_history": [
            {
                "session_id": 1,
                "subtitle_cue_id": 1,
                "label_key": "misheard",
                "transcript_excerpt": "hello there",
                "heard_as": "hello bear",
                "note": "confused vowel sound",
                "created_at": "2026-07-24 12:00:00",
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "confused vowel sound" in md


def test_render_markdown_current_annotations_note_survives():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "current_material_annotations": [
            {
                "subtitle_cue_id": 1,
                "label_key": "unknown_chunk",
                "transcript_excerpt": "kind of",
                "heard_as": None,
                "note": "still unsure of meaning",
            }
        ],
    }
    md = fmt.render_markdown(_bundle([material]))
    assert "still unsure of meaning" in md


# ---- Category omission still works ----


def test_render_markdown_omits_quick_practice_section_when_category_not_selected():
    material = {"title": "Lesson", "material_id": 1}
    md = fmt.render_markdown(_bundle([material]))
    assert "Quick Practice" not in md


# ---- Redaction parity across formats ----


def test_render_markdown_and_json_show_redaction_placeholder_consistently():
    material = {
        "title": "Lesson",
        "material_id": 1,
        "quick_practice_evidence": [
            {
                "session_id": 1,
                "source_type": "recent",
                "status": "completed",
                "requested_count": 1,
                "actual_count": 1,
                "started_at": "2026-07-24 12:00:00",
                "completed_at": "2026-07-24 12:01:00",
                "abandoned_at": None,
                "items": [
                    {
                        "position": 1,
                        "subtitle_cue_id": 1,
                        "recall_result": "recalled",
                        "heard_fragment": "[redacted]",
                        "completed": True,
                        "shadowed": False,
                        "diagnosis": [],
                    }
                ],
            }
        ],
    }
    bundle = _bundle([material])
    md = fmt.render_markdown(bundle)
    js = json.loads(fmt.render_json(bundle))
    assert "redacted" in md
    assert js["materials"][0]["quick_practice_evidence"][0]["items"][0]["heard_fragment"] == "[redacted]"


# ---- Semantic coverage: every material key the export service can produce
# must render *something* distinguishable in Markdown, so a future evidence
# category added to `export_service.py` without a matching Markdown branch
# fails this test loudly instead of silently becoming JSON-only. ----


def test_render_markdown_has_a_visible_marker_for_every_known_material_key():
    marker_by_key = {
        "material_metadata": "MARKERMATERIALMETADATA",
        "sessions": "MARKERSESSIONRESPONSE",
        "session_diagnosis_history": "MARKERDIAGNOSISNOTE",
        "current_material_annotations": "MARKERANNOTATIONNOTE",
        "quiz_attempts": "MARKERQUIZLEARNERANSWER",
        "shadowing_evidence": "MARKERSHADOWINGEXCERPT",
        "retained_recordings": 424242,
        "cue_notes": "MARKERCUENOTE",
        "vocabulary_and_saved_chunks": "MARKERVOCABTEXT",
        "quick_practice_evidence": "MARKERQUICKPRACTICEHEARDFRAGMENT",
    }
    material = {
        "title": "Lesson",
        "material_id": 1,
        "material_metadata": {"language": marker_by_key["material_metadata"], "source_label": "audio file"},
        "sessions": [
            {
                "session_id": 1,
                "status": "completed",
                "mode": "intensive",
                "stage_responses": [
                    {"stage_key": "global_comprehension", "prompt_key": "p", "response_text": marker_by_key["sessions"]}
                ],
                "keyword_captures": [],
            }
        ],
        "session_diagnosis_history": [
            {
                "session_id": 1,
                "subtitle_cue_id": 1,
                "label_key": "misheard",
                "transcript_excerpt": "x",
                "heard_as": "y",
                "note": marker_by_key["session_diagnosis_history"],
                "created_at": "2026-07-24 12:00:00",
            }
        ],
        "current_material_annotations": [
            {
                "subtitle_cue_id": 1,
                "label_key": "misheard",
                "transcript_excerpt": "x",
                "heard_as": "y",
                "note": marker_by_key["current_material_annotations"],
            }
        ],
        "quiz_attempts": [
            {
                "attempt_id": 1,
                "quiz_mode": "dictation",
                "completed_at": "2026-07-24 12:00:00",
                "correct_count": 1,
                "actual_count": 1,
                "accuracy": 1.0,
                "questions": [
                    {
                        "position": 1,
                        "question_type": "dictation",
                        "source_cue_text": "x",
                        "prompt": {"masked_text": "x"},
                        "correct_answer": {"answer_text": "x"},
                        "learner_answer": {
                            "raw_answer_text": marker_by_key["quiz_attempts"],
                            "selected_choice_index": None,
                            "is_correct": True,
                        },
                    }
                ],
            }
        ],
        "shadowing_evidence": [
            {
                "transcript_excerpt": marker_by_key["shadowing_evidence"],
                "practice_count": 1,
                "last_practiced_at": "2026-07-24 12:00:00",
            }
        ],
        "retained_recordings": [
            {
                "recording_id": marker_by_key["retained_recordings"],
                "duration_ms": 1000,
                "status": "ready",
                "created_at": "2026-07-24 12:00:00",
            }
        ],
        "cue_notes": [{"transcript_excerpt": "x", "note": marker_by_key["cue_notes"]}],
        "vocabulary_and_saved_chunks": [
            {"item_type": "word", "text": marker_by_key["vocabulary_and_saved_chunks"], "meaning": "m"}
        ],
        "quick_practice_evidence": [
            {
                "session_id": 1,
                "source_type": "recent",
                "status": "completed",
                "requested_count": 1,
                "actual_count": 1,
                "started_at": "2026-07-24 12:00:00",
                "completed_at": "2026-07-24 12:01:00",
                "abandoned_at": None,
                "items": [
                    {
                        "position": 1,
                        "subtitle_cue_id": 1,
                        "recall_result": "recalled",
                        "heard_fragment": marker_by_key["quick_practice_evidence"],
                        "completed": True,
                        "shadowed": False,
                        "diagnosis": [],
                    }
                ],
            }
        ],
    }

    md = fmt.render_markdown(_bundle([material]))

    for key, marker in marker_by_key.items():
        assert str(marker) in md, f"material key {key!r} has no visible Markdown representation"


# ---- JSON ----


def test_render_json_is_valid_and_contains_export_version():
    js = fmt.render_json(_bundle())
    parsed = json.loads(js)
    assert parsed["export_version"] == 1
    assert parsed["scope_description"] == "All Materials"


def test_render_json_round_trips_material_data_exactly():
    material = {"title": "Lesson", "material_id": 1, "quiz_attempts": [{"attempt_id": 1, "accuracy": 0.5}]}
    js = fmt.render_json(_bundle([material]))
    parsed = json.loads(js)
    assert parsed["materials"] == [material]


def test_preview_and_saved_output_are_identical_for_the_same_bundle():
    bundle = _bundle([{"title": "Lesson", "material_id": 1}])
    first_markdown = fmt.render_markdown(bundle)
    second_markdown = fmt.render_markdown(bundle)
    assert first_markdown == second_markdown
    first_json = fmt.render_json(bundle)
    second_json = fmt.render_json(bundle)
    assert first_json == second_json


# ---- evaluation template ----


def test_evaluation_template_states_key_limitations():
    template = fmt.render_evaluation_template()
    assert "different questions" in template
    assert "effective study time" in template
    assert "pronunciation" in template
    assert "improvement" in template


def test_evaluation_template_with_bundle_includes_scope_header():
    template = fmt.render_evaluation_template(_bundle())
    assert "All Materials" in template
    assert "All Time" in template
