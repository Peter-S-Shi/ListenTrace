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
