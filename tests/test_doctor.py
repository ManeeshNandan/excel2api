from pathlib import Path

from excel2api.doctor import validate_sync_config


def test_doctor_accepts_valid_config(tmp_path: Path):
    workbook = tmp_path / "data.csv"
    workbook.write_text("Name\nJohn\n", encoding="utf-8")
    schema = tmp_path / "schema.yaml"
    schema.write_text("fields:\n  name:\n    column: Name\n    type: string\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        "input: data.csv\nschema: schema.yaml\napi:\n  base_url: https://example.test/api\n",
        encoding="utf-8",
    )
    assert validate_sync_config(config) == []


def test_doctor_detects_missing_schema(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        "input: data.csv\nschema: missing.yaml\napi:\n  base_url: https://example.test/api\n",
        encoding="utf-8",
    )
    (tmp_path / "data.csv").write_text("Name\nJohn\n", encoding="utf-8")
    problems = validate_sync_config(config)
    assert any("Schema file not found" in p for p in problems)
