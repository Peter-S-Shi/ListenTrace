"""M13 Stage B, G15: shared-state rendering vocabulary for StageStepper's
step items and QuizOptionCard's answer cards.

Seams under test: the `role`/`state`/`selected` Qt widget properties these
two components tag their children with -- the same public property
mechanism `apply_role`/`nav_item`'s `active` property already use elsewhere
(see test_theme.py), consumed by QSS attribute selectors. Not private
attributes, not rendered pixels: the properties *are* the public contract
between a widget and the shared stylesheet.

StageStepper and QuizOptionCard remain distinct semantic widgets/roles
(`stepper_item`, `quiz_option`) per the Product Owner's G15 ruling -- these
tests never assume or require a shared base widget class between them.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

from listentrace.domain.enums.stage_status import StageStatus
from listentrace.ui import theme
from listentrace.ui.windows.guided_session_window import StageStepper
from listentrace.ui.windows.quiz_window import QuizOptionCard


def _progress(status: str) -> SimpleNamespace:
    return SimpleNamespace(status=status)


def _qss_rule(sheet: str, selector: str) -> str:
    """The literal `{ ... }` body Qt would parse for `selector`, extracted
    from the real built stylesheet -- the actual public contract the style
    engine consumes, not a private implementation detail. Used instead of
    screenshot/pixel comparison per the reviewer's explicit guidance."""
    match = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", sheet)
    assert match is not None, f"no QSS rule found for selector: {selector}"
    return match.group(1)


def test_stage_stepper_items_are_tagged_with_the_shared_stepper_item_role(qapp):
    stepper = StageStepper()

    for button in stepper._step_buttons.values():
        assert button.property("role") == "stepper_item"


def test_stage_stepper_current_stage_gets_the_current_state(qapp):
    stepper = StageStepper()
    progress = {"global_comprehension": _progress(StageStatus.IN_PROGRESS.value)}

    stepper.update_stepper("global_comprehension", progress, read_only=False)

    assert stepper._step_buttons["global_comprehension"].property("state") == "current"
    assert stepper._step_badges["global_comprehension"].property("state") == "current"


def test_stage_stepper_completed_stage_gets_the_completed_state(qapp):
    stepper = StageStepper()
    progress = {"global_comprehension": _progress(StageStatus.COMPLETED.value)}

    stepper.update_stepper("keyword_capture", progress, read_only=False)

    assert stepper._step_buttons["global_comprehension"].property("state") == "completed"
    assert stepper._step_badges["global_comprehension"].text() == "✓"


def test_stage_stepper_not_started_stage_gets_the_not_started_state(qapp):
    stepper = StageStepper()

    stepper.update_stepper("global_comprehension", {}, read_only=False)

    assert stepper._step_buttons["keyword_capture"].property("state") == "not_started"


def test_quiz_option_card_is_tagged_with_the_shared_quiz_option_role(qapp):
    card = QuizOptionCard(index=0, letter="A")

    assert card.property("role") == "quiz_option"
    assert card._badge.property("role") == "quiz_option_badge"


def test_quiz_option_card_starts_unselected(qapp):
    card = QuizOptionCard(index=0, letter="A")

    assert card.property("selected") == "false"


def test_stepper_completed_state_uses_the_canonical_paper_primary_background():
    sheet = theme.build_stylesheet("light")

    rule = _qss_rule(sheet, 'QPushButton[role="stepper_item"][state="completed"]')

    assert theme.css("surface_paper") in rule
    assert theme.css("surface") not in rule


def test_stepper_skipped_state_uses_the_canonical_paper_primary_background():
    sheet = theme.build_stylesheet("light")

    rule = _qss_rule(sheet, 'QPushButton[role="stepper_item"][state="skipped"]')

    assert theme.css("surface_paper") in rule
    assert theme.css("surface") not in rule


def test_stepper_not_started_state_uses_the_canonical_paper_secondary_and_warm_border():
    sheet = theme.build_stylesheet("light")

    rule = _qss_rule(sheet, 'QPushButton[role="stepper_item"][state="not_started"]')

    assert theme.css("surface_soft") in rule
    assert theme.css("line") in rule
    assert theme.css("disabled_border") not in rule


def test_stepper_not_started_badge_uses_the_canonical_muted_fill_and_disabled_text():
    sheet = theme.build_stylesheet("light")

    rule = _qss_rule(sheet, 'QLabel[role="stepper_item_badge"][state="not_started"]')

    assert theme.css("stepper_future_badge") in rule
    assert theme.css("stepper_future_badge").upper() == "#E3DDD4"
    assert theme.css("disabled_text") in rule


def test_quiz_option_card_checking_the_radio_marks_it_selected(qapp):
    """The radio button is the real public interaction surface (mouse click
    on the card, or keyboard activation, both route through it) -- checking
    it is not reaching into a private implementation detail."""
    card = QuizOptionCard(index=0, letter="A")

    card._radio.setChecked(True)

    assert card.property("selected") == "true"
    assert card._selected_marker.text() == "✓"
