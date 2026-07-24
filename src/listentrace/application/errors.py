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
