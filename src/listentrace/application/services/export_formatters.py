from __future__ import annotations

import dataclasses
import json

from listentrace.application.dto.export import ExportBundle

"""Pure, framework-free formatters for Milestone 9. Every function here takes
an already-built `ExportBundle` (see `export_service.build_export`) and
returns a string — none of them touch a database connection or Qt, and none
of them re-derive data the bundle doesn't already carry. Preview and saved
output are guaranteed identical because both call the same function on the
same bundle (see `ui/windows/export_dialog.py`)."""

# ---- Markdown ----

# The minimal set of characters that can hijack Markdown structure when they
# appear inside arbitrary learner-entered text. Deliberately narrow: normal
# sentence punctuation (periods, commas, mid-sentence hyphens) is left alone
# so exported text stays readable, per the milestone's "readable Markdown"
# requirement.
_INLINE_ESCAPE_CHARS = "\\`*_[]<>|"
_LINE_START_ESCAPE_CHARS = ("#", "-", "+", ">", "*")


def escape_markdown_line(text: str) -> str:
    escaped_chars = []
    for ch in text:
        if ch in _INLINE_ESCAPE_CHARS:
            escaped_chars.append("\\")
        escaped_chars.append(ch)
    result = "".join(escaped_chars)
    if result[:1] in _LINE_START_ESCAPE_CHARS:
        result = "\\" + result
    return result


def escape_markdown_multiline(text: str) -> str:
    """Preserves line breaks — each line is escaped independently, since a
    line-start character (e.g. `-`) is only structurally significant at the
    start of *its own* line, not the start of the whole field."""
    return "\n".join(escape_markdown_line(line) for line in text.split("\n"))


def _md_line(label: str, value) -> str:
    if value is None or value == "":
        return f"- **{label}:** _(none)_"
    return f"- **{label}:** {escape_markdown_line(str(value))}"


def _md_blockquote(label: str, value: str | None) -> str:
    escaped_label = escape_markdown_line(label)
    if not value:
        return f"**{escaped_label}:** _(none)_\n"
    quoted = "\n".join(f"> {line}" for line in escape_markdown_multiline(value).split("\n"))
    return f"**{escaped_label}:**\n\n{quoted}\n"


def render_markdown(bundle: ExportBundle) -> str:
    lines: list[str] = []
    lines.append("# ListenTrace Learning Evidence Export")
    lines.append("")
    lines.append(f"- **Export timestamp (UTC):** {bundle.generated_at}")
    lines.append(f"- **Export version:** {bundle.export_version}")
    lines.append(f"- **Scope:** {escape_markdown_line(bundle.scope_description)}")
    lines.append(f"- **Date range:** {escape_markdown_line(bundle.date_range_description)}")
    lines.append(f"- **Included evidence categories:** {', '.join(bundle.categories) or '(none)'}")
    lines.append(f"- **Included privacy fields:** {', '.join(bundle.privacy_fields) or '(none)'}")
    lines.append("")
    lines.append(f"> {bundle.timestamp_convention}")
    lines.append("")
    lines.append(
        f"**Contents:** {len(bundle.materials)} material(s) exported."
        if bundle.materials
        else "**Contents:** no materials matched the selected scope and filters."
    )
    lines.append("")

    for material in bundle.materials:
        lines.extend(_render_material_markdown(material))

    return "\n".join(lines) + "\n"


def _render_material_markdown(material: dict) -> list[str]:
    lines = [f"## {escape_markdown_line(material['title'])}", ""]

    if "material_metadata" in material:
        meta = material["material_metadata"]
        lines.append("### Material Metadata")
        lines.append(_md_line("Language", meta.get("language")))
        lines.append(_md_line("Media kind", meta.get("media_kind")))
        lines.append(_md_line("Duration (ms)", meta.get("duration_ms")))
        lines.append(_md_line("Imported", meta.get("created_at")))
        lines.append(_md_line("Status", meta.get("status")))
        lines.append(_md_line("Transcript capability", meta.get("subtitle_capability")))
        if "source_label" in meta:
            lines.append(_md_line("Source", meta.get("source_label")))
        lines.append("")

    if "sessions" in material:
        lines.append("### Sessions")
        if not material["sessions"]:
            lines.append("_No sessions in scope._")
            lines.append("")
        for session in material["sessions"]:
            lines.append(f"#### Session #{session['session_id']} — {session['status']}")
            if "current_stage" in session:
                lines.append(_md_line("Mode", session.get("mode")))
                lines.append(_md_line("Current stage", session.get("current_stage")))
                lines.append(_md_line("Started", session.get("started_at")))
                lines.append(_md_line("Completed", session.get("completed_at")))
                lines.append(_md_line("Abandoned", session.get("abandoned_at")))
                lines.append("")
                lines.append("| Stage | Status | Skip note |")
                lines.append("|---|---|---|")
                for stage in session.get("stages", []):
                    note = escape_markdown_line(stage["skip_note"]) if stage["skip_note"] else ""
                    lines.append(f"| {stage['stage_key']} | {stage['status']} | {note} |")
                lines.append("")
            if "stage_responses" in session:
                for response in session["stage_responses"]:
                    lines.append(_md_blockquote(f"{response['stage_key']} / {response['prompt_key']}", response["response_text"]))
                if session.get("keyword_captures"):
                    lines.append("**Keyword captures:**")
                    for capture in session["keyword_captures"]:
                        lines.append(f"- ({capture['capture_type']}) {escape_markdown_line(capture['text'])}")
                    lines.append("")

    if "session_diagnosis_history" in material:
        lines.append("### Session Diagnosis History")
        rows = material["session_diagnosis_history"]
        if not rows:
            lines.append("_No session diagnosis evidence in scope._")
        else:
            lines.append("| Session | Label | Transcript excerpt | Heard as | Recorded |")
            lines.append("|---|---|---|---|---|")
            for row in rows:
                lines.append(
                    f"| #{row['session_id']} | {row['label_key']} | "
                    f"{escape_markdown_line(row['transcript_excerpt'] or '')} | "
                    f"{escape_markdown_line(row['heard_as'] or '')} | {row['created_at']} |"
                )
        lines.append("")

    if "current_material_annotations" in material:
        lines.append("### Current Material Annotations (present state, not history)")
        rows = material["current_material_annotations"]
        if not rows:
            lines.append("_No current annotations._")
        else:
            lines.append("| Label | Transcript excerpt | Heard as |")
            lines.append("|---|---|---|")
            for row in rows:
                lines.append(
                    f"| {row['label_key']} | {escape_markdown_line(row['transcript_excerpt'] or '')} | "
                    f"{escape_markdown_line(row['heard_as'] or '')} |"
                )
        lines.append("")

    if "quiz_attempts" in material:
        lines.append("### Quiz Attempts (completed only)")
        rows = material["quiz_attempts"]
        if not rows:
            lines.append("_No completed quiz attempts in scope._")
        else:
            lines.append("| Attempt | Mode | Completed | Score | Accuracy |")
            lines.append("|---|---|---|---|---|")
            for row in rows:
                accuracy = f"{row['accuracy']:.0%}" if row["accuracy"] is not None else "n/a"
                lines.append(
                    f"| #{row['attempt_id']} | {row['quiz_mode']} | {row['completed_at']} | "
                    f"{row['correct_count']}/{row['actual_count']} | {accuracy} |"
                )
                if row.get("question_type_breakdown"):
                    breakdown = ", ".join(
                        f"{b['question_type']}: {b['correct_count']}/{b['question_count']}"
                        for b in row["question_type_breakdown"]
                    )
                    lines.append(f"  - Breakdown: {escape_markdown_line(breakdown)}")
                if "questions" in row:
                    for q in row["questions"]:
                        lines.append(
                            f"  - Q{q['position']} ({q['question_type']}): "
                            f"{escape_markdown_line(q['source_cue_text'])}"
                        )
        lines.append("")

    if "shadowing_evidence" in material:
        lines.append("### Shadowing Evidence")
        rows = material["shadowing_evidence"]
        if not rows:
            lines.append("_No shadowing practice in scope._")
        else:
            lines.append("| Transcript excerpt | Practice count | Last practiced |")
            lines.append("|---|---|---|")
            for row in rows:
                lines.append(
                    f"| {escape_markdown_line(row['transcript_excerpt'] or '')} | {row['practice_count']} | "
                    f"{row['last_practiced_at']} |"
                )
        lines.append("")

    if "retained_recordings" in material:
        lines.append("### Retained Recordings (metadata only)")
        rows = material["retained_recordings"]
        if not rows:
            lines.append("_No retained recordings in scope._")
        else:
            lines.append("| Recording | Duration (ms) | Status | Recorded |")
            lines.append("|---|---|---|---|")
            for row in rows:
                lines.append(f"| #{row['recording_id']} | {row['duration_ms']} | {row['status']} | {row['created_at']} |")
        lines.append("")

    if "cue_notes" in material:
        lines.append("### Learner Notes")
        rows = material["cue_notes"]
        if not rows:
            lines.append("_No cue notes in scope._")
        else:
            for row in rows:
                lines.append(_md_blockquote(row["transcript_excerpt"] or "Note", row["note"]))
        lines.append("")

    if "vocabulary_and_saved_chunks" in material:
        lines.append("### Vocabulary and Saved Chunks")
        rows = material["vocabulary_and_saved_chunks"]
        if not rows:
            lines.append("_No saved vocabulary or chunks._")
        else:
            lines.append("| Type | Text | Meaning |")
            lines.append("|---|---|---|")
            for row in rows:
                lines.append(
                    f"| {row['item_type']} | {escape_markdown_line(row['text'])} | "
                    f"{escape_markdown_line(row['meaning'] or '')} |"
                )
        lines.append("")

    return lines


# ---- JSON ----


def render_json(bundle: ExportBundle) -> str:
    return json.dumps(dataclasses.asdict(bundle), ensure_ascii=False, indent=2)


# ---- external evaluation template ----

_EVALUATION_TEMPLATE = """\
# ListenTrace External Evaluation Instructions

This document accompanies a ListenTrace learning-evidence export (Markdown \
or JSON). Use it to guide a careful, evidence-based review of the learner's \
foreign-language listening practice.

## Your Task

1. Summarize the learner's overall practice record from the supplied evidence.
2. Identify recurring diagnosis categories (e.g. misheard words, connected/\
reduced speech, unknown chunks) and where they concentrate.
3. Compare quiz attempts cautiously — note that different attempts may use \
different questions and different question counts, so raw score \
differences are not directly comparable across attempts.
4. Identify materials that may need further practice, citing the specific \
evidence that supports each one.
5. Suggest concrete, actionable exercises tied to the recurring categories \
you identified.
6. Cite the supplied evidence for every claim you make.
7. Label any interpretation you are uncertain about as uncertain, and \
clearly distinguish evidence (what is directly recorded) from inference \
(your own reasoning about it).
8. Do not invent data that is not present in the export. If a category is \
absent or a section is empty, say so rather than guessing.

## Important Limitations of This Data

- Quiz attempts may use different, independently generated questions — a \
score difference between two attempts is not proof of improvement or \
decline.
- Timestamps record when events happened; they are not a measure of \
effective study time or practice duration.
- Recording metadata (duration, count, status) does not assess \
pronunciation, accent, or spoken accuracy in any way.
- A rising or falling practice count does not by itself prove or disprove \
improvement.

Treat every number in this export as evidence to be interpreted, not as a \
finished verdict.
"""


def render_evaluation_template(bundle: ExportBundle | None = None) -> str:
    if bundle is None:
        return _EVALUATION_TEMPLATE
    header = (
        f"_Prepared for a ListenTrace export — scope: {bundle.scope_description}; "
        f"date range: {bundle.date_range_description}._\n\n"
    )
    return header + _EVALUATION_TEMPLATE
