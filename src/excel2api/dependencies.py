from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .report import extract_path
from .schema import load_schema


@dataclass(frozen=True)
class ReferenceSpec:
    target_field: str
    source_sheet: str
    source_key: str
    target_key: str
    source_value: str


def parse_references(sheet_cfg: dict[str, Any]) -> list[ReferenceSpec]:
    refs = sheet_cfg.get("references", []) or []
    if not isinstance(refs, list):
        raise ValueError("references must be a list")
    result = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("each reference must be a mapping")
        required = ("target_field", "source_sheet", "source_key", "target_key", "source_value")
        missing = [key for key in required if not ref.get(key)]
        if missing:
            raise ValueError(f"reference missing required fields: {', '.join(missing)}")
        result.append(ReferenceSpec(**{key: ref[key] for key in required}))
    return result


def dependency_order(sheets: dict[str, dict[str, Any]]) -> list[str]:
    graph = {name: set() for name in sheets}
    for name, cfg in sheets.items():
        for ref in parse_references(cfg or {}):
            if ref.source_sheet not in sheets:
                raise ValueError(f"Sheet '{name}' references unknown sheet '{ref.source_sheet}'")
            if ref.source_sheet == name:
                raise ValueError(f"Sheet '{name}' cannot depend on itself")
            graph[name].add(ref.source_sheet)

    ordered = []
    remaining = {name: set(deps) for name, deps in graph.items()}
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"Circular sheet dependency detected involving: {cycle}")
        ordered.extend(ready)
        for name in ready:
            remaining.pop(name)
        for deps in remaining.values():
            deps.difference_update(ready)
    return ordered


def build_reference_indexes(
    sheet_name: str,
    results: list[Any],
    response_mapping: dict[str, str],
) -> dict[str, dict[Any, Any]]:
    indexes: dict[str, dict[Any, Any]] = {}
    for result in results:
        if not result.success or not result.record:
            continue
        for key_name in {
            key for key in result.record.keys()
        }:
            indexes.setdefault(key_name, {})[result.record.get(key_name)] = result.response
    return indexes


def resolve_overrides(
    input_path: str,
    sheet_name: str,
    sheet_cfg: dict[str, Any],
    results_by_sheet: dict[str, list[Any]],
) -> dict[int, dict[str, Any]]:
    """Build row-numbered target-field overrides from completed dependency sheets."""
    refs = parse_references(sheet_cfg)
    if not refs:
        return {}

    target_fields = {f.name: f.column for f in load_schema(sheet_cfg["schema"])}
    all_rows = __import__("excel2api.reader", fromlist=["read_file"]).read_file(input_path, sheet_name=sheet_name)
    overrides: dict[int, dict[str, Any]] = {}

    for ref in refs:
        if ref.target_field not in target_fields:
            raise ValueError(f"Reference target field '{ref.target_field}' is not in sheet '{sheet_name}' schema")
        source_results = results_by_sheet.get(ref.source_sheet)
        if source_results is None:
            raise ValueError(f"Dependency '{ref.source_sheet}' has not been processed")

        source_map: dict[Any, Any] = {}
        source_mapping = {}
        # Read the dependency's configured response mapping if present.
        source_cfg = sheet_cfg.get("_all_sheets", {}).get(ref.source_sheet, {}) if isinstance(sheet_cfg.get("_all_sheets"), dict) else {}
        source_mapping = (source_cfg.get("response", {}) or {}).get("mapping", {}) or {}
        if ref.source_value in source_mapping:
            response_path = source_mapping[ref.source_value]
        else:
            response_path = ref.source_value

        for result in source_results:
            if not result.success or not result.record:
                continue
            key = result.record.get(ref.source_key)
            value = extract_path(result.response, response_path, None)
            if key is not None and value is not None:
                source_map[key] = value

        for row_number, raw_row in enumerate(all_rows, start=2):
            target_key = raw_row.get(target_fields.get(ref.target_key, ref.target_key))
            if target_key in source_map:
                overrides.setdefault(row_number, {})[ref.target_field] = source_map[target_key]
    return overrides
