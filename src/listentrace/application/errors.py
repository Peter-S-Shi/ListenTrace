from __future__ import annotations


class MaterialValidationError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


class MaterialNotFoundError(Exception):
    def __init__(self, material_id: int):
        self.material_id = material_id
        super().__init__(f"Material {material_id} not found")


class PlayerOpenError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


class CueNotFoundError(Exception):
    def __init__(self, subtitle_cue_id: int):
        self.subtitle_cue_id = subtitle_cue_id
        super().__init__(f"Subtitle cue {subtitle_cue_id} not found")


class AnnotationValidationError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


class AnnotationNotFoundError(Exception):
    def __init__(self, annotation_id: int):
        self.annotation_id = annotation_id
        super().__init__(f"Annotation {annotation_id} not found")


class SavedItemValidationError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


class SavedItemNotFoundError(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id
        super().__init__(f"Saved language item {item_id} not found")


class SessionNotFoundError(Exception):
    def __init__(self, session_id: int):
        self.session_id = session_id
        super().__init__(f"Practice session {session_id} not found")


class ActiveSessionExistsError(Exception):
    def __init__(self, material_id: int, active_session_id: int):
        self.material_id = material_id
        self.active_session_id = active_session_id
        super().__init__(
            f"Material {material_id} already has an active intensive session ({active_session_id})"
        )


class SessionValidationError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


class DiagnosisNotFoundError(Exception):
    def __init__(self, evidence_id: int):
        self.evidence_id = evidence_id
        super().__init__(f"Session diagnosis {evidence_id} not found")


class KeywordCaptureNotFoundError(Exception):
    def __init__(self, capture_id: int):
        self.capture_id = capture_id
        super().__init__(f"Keyword capture {capture_id} not found")
