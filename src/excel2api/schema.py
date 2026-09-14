from dataclasses import dataclass, field
from pathlib import Path
import yaml


SUPPORTED_TYPES = {
    "string", "integer", "float", "decimal",
    "boolean", "date", "datetime", "email", "phone"
}


@dataclass
class Field:
    name: str
    column: str
    type: str = "string"
    required: bool = False
    nullable: bool = True
    default: object = None
    options: list[object] = field(default_factory=list)
    min_length: int | None = None
    max_length: int | None = None
    minimum: float | None = None
    maximum: float | None = None
    regex: str | None = None
    transform: list[str] = field(default_factory=list)
    include: bool = True


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    fields = []
    for name, config in data.get("fields", {}).items():
        config = config or {}
        field_type = config.get("type", "string")

        if field_type not in SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported type '{field_type}' for field '{name}'. "
                f"Supported types: {', '.join(sorted(SUPPORTED_TYPES))}"
            )

        fields.append(Field(
            name=name,
            column=config.get("column", name),
            type=field_type,
            required=config.get("required", False),
            nullable=config.get("nullable", True),
            default=config.get("default"),
            options=config.get("options", []),
            min_length=config.get("min_length"),
            max_length=config.get("max_length"),
            minimum=config.get("min"),
            maximum=config.get("max"),
            regex=config.get("regex"),
            transform=config.get("transform", []),
            include=config.get("include", True),
        ))

    if not fields:
        raise ValueError("Schema must contain at least one field")

    return {"fields": fields, "response": data.get("response", {}) or {}}


def load_schema(path: str | Path) -> list[Field]:
    return load_config(path)["fields"]
