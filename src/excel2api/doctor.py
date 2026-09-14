from pathlib import Path
from typing import Any

from .config import load_sync_config
from .reader import list_sheets
from .schema import load_schema
from .dependencies import dependency_order


def validate_sync_config(path: str | Path) -> list[str]:
    """Return configuration problems; an empty list means the config is healthy."""
    config_path = Path(path).resolve()
    cfg = load_sync_config(config_path)
    problems: list[str] = []
    base = config_path.parent

    def resolve(value: Any) -> Path:
        p = Path(str(value))
        return p if p.is_absolute() else base / p

    input_value = cfg.get("input")
    if input_value:
        input_path = resolve(input_value)
        if not input_path.exists():
            problems.append(f"Input file not found: {input_path}")
        elif input_path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            problems.append(f"Unsupported input format: {input_path.suffix}")
    elif not cfg.get("sheets"):
        problems.append("Missing config.input")

    api = cfg.get("api", {}) or {}
    if not api.get("base_url") and not cfg.get("sheets"):
        problems.append("Missing api.base_url")

    sheets = cfg.get("sheets", {}) or {}
    try:
        dependency_order(sheets)
    except ValueError as exc:
        problems.append(str(exc))

    for sheet_name, spec in sheets.items():
        schema_path = resolve(spec.get("schema", ""))
        if not schema_path.exists():
            problems.append(f"Schema for sheet '{sheet_name}' not found: {schema_path}")
        else:
            try:
                load_schema(schema_path)
            except Exception as exc:
                problems.append(f"Invalid schema for sheet '{sheet_name}': {exc}")
        if input_value and Path(str(input_value)).suffix.lower() in {".xlsx", ".xls"}:
            try:
                names = list_sheets(resolve(input_value))
                if sheet_name not in names:
                    problems.append(f"Sheet '{sheet_name}' not found in workbook")
            except Exception as exc:
                problems.append(f"Cannot inspect workbook: {exc}")

    if not sheets and cfg.get("schema"):
        schema_path = resolve(cfg["schema"])
        if not schema_path.exists():
            problems.append(f"Schema file not found: {schema_path}")
        else:
            try:
                load_schema(schema_path)
            except Exception as exc:
                problems.append(f"Invalid schema: {exc}")
    elif not sheets and not cfg.get("schema"):
        problems.append("Missing config.schema")

    for operation, spec in (api.get("endpoints", {}) or {}).items():
        if not isinstance(spec, (str, dict)):
            problems.append(f"Endpoint '{operation}' must be a string or mapping")
            continue
        if isinstance(spec, dict) and not spec.get("method"):
            problems.append(f"Endpoint '{operation}' is missing method")
        if isinstance(spec, dict) and "path" not in spec:
            problems.append(f"Endpoint '{operation}' is missing path")

    return problems
