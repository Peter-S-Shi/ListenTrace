from __future__ import annotations

from dataclasses import dataclass, field

SCOPE_ALL = "all"
SCOPE_ONE_MATERIAL = "one_material"
SCOPE_SELECTED_MATERIALS = "selected_materials"


@dataclass(slots=True, frozen=True)
class ExportScope:
    kind: str  # SCOPE_ALL | SCOPE_ONE_MATERIAL | SCOPE_SELECTED_MATERIALS
    material_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in (SCOPE_ALL, SCOPE_ONE_MATERIAL, SCOPE_SELECTED_MATERIALS):
            raise ValueError(f"Unknown export scope kind: {self.kind!r}")
        if self.kind == SCOPE_ONE_MATERIAL and len(self.material_ids) != 1:
            raise ValueError("SCOPE_ONE_MATERIAL requires exactly one material id")
        if self.kind == SCOPE_SELECTED_MATERIALS and not self.material_ids:
            raise ValueError("SCOPE_SELECTED_MATERIALS requires at least one material id")
        if self.kind == SCOPE_ALL and self.material_ids:
            raise ValueError("SCOPE_ALL must not carry material ids")


@dataclass(slots=True, frozen=True)
class ExportBundle:
    """The single, already-generated result both the Markdown and JSON
    formatters render from (see `export_formatters.py`) — never regenerated
    between preview and save, so the two can never show different data for
    the same export (see `export_service.build_export`)."""

    export_version: int
    generated_at: str
    timestamp_convention: str
    scope_description: str
    date_range_description: str
    categories: list[str]
    privacy_fields: list[str]
    materials: list[dict] = field(default_factory=list)
