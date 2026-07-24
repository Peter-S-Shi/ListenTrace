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
