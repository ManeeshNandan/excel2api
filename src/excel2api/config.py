from pathlib import Path
import yaml


def load_sync_config(path: str | Path) -> dict:
    """Load and validate a sync configuration file."""
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError("Sync config must be a YAML mapping")

    for section in ("api", "sync", "response"):
        value = data.get(section, {}) or {}
        if not isinstance(value, dict):
            raise ValueError(f"{section} section must be a mapping")

    sheets = data.get("sheets", {}) or {}
    if sheets and not isinstance(sheets, dict):
        raise ValueError("sheets section must be a mapping")
    for name, spec in sheets.items():
        if not isinstance(spec, dict):
            raise ValueError(f"Sheet '{name}' configuration must be a mapping")
        if not spec.get("schema"):
            raise ValueError(f"Sheet '{name}' must define a schema")
        refs = spec.get("references", []) or []
        if not isinstance(refs, list):
            raise ValueError(f"Sheet '{name}' references must be a list")

    return data
