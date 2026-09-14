import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from .errors import ValidationError


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s-]{6,19}$")


def is_empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def convert(value, field_type):
    if value is None:
        return None

    if field_type == "string":
        return str(value).strip()

    if field_type == "integer":
        return int(value)

    if field_type == "float":
        return float(value)

    if field_type == "decimal":
        return float(Decimal(str(value)))

    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
        raise ValueError("must be a boolean")

    if field_type == "date":
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        return datetime.fromisoformat(str(value)).date().isoformat()

    if field_type == "datetime":
        if isinstance(value, datetime):
            return value.isoformat()
        return datetime.fromisoformat(str(value)).isoformat()

    if field_type in {"email", "phone"}:
        return str(value).strip()

    raise ValueError(f"unsupported type: {field_type}")


def apply_transforms(value, transforms):
    for transform in transforms:
        if value is None:
            break
        if transform == "strip":
            value = str(value).strip()
        elif transform == "uppercase":
            value = str(value).upper()
        elif transform == "lowercase":
            value = str(value).lower()
        else:
            raise ValueError(f"unknown transform: {transform}")
    return value


def validate_and_convert(row: dict, fields: list[object], row_number: int):
    output = {}
    errors = []

    for field in fields:
        value = row.get(field.column)

        if is_empty(value):
            if field.required:
                errors.append(ValidationError(
                    row_number, field.name, "required field is missing"
                ))
                continue

            if field.default is not None:
                value = field.default
            elif field.nullable:
                output[field.name] = None
                continue
            else:
                errors.append(ValidationError(
                    row_number, field.name, "null value is not allowed"
                ))
                continue

        try:
            value = apply_transforms(value, field.transform)
            value = convert(value, field.type)
        except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
            errors.append(ValidationError(row_number, field.name, str(exc)))
            continue

        if field.type == "email" and not EMAIL_RE.match(value):
            errors.append(ValidationError(
                row_number, field.name, "invalid email address"
            ))
            continue

        if field.type == "phone" and not PHONE_RE.match(value):
            errors.append(ValidationError(
                row_number, field.name, "invalid phone number"
            ))
            continue

        if field.min_length is not None and len(value) < field.min_length:
            errors.append(ValidationError(
                row_number, field.name,
                f"length must be at least {field.min_length}"
            ))
            continue

        if field.max_length is not None and len(value) > field.max_length:
            errors.append(ValidationError(
                row_number, field.name,
                f"length must be at most {field.max_length}"
            ))
            continue

        if field.minimum is not None and value < field.minimum:
            errors.append(ValidationError(
                row_number, field.name, f"value must be >= {field.minimum}"
            ))
            continue

        if field.maximum is not None and value > field.maximum:
            errors.append(ValidationError(
                row_number, field.name, f"value must be <= {field.maximum}"
            ))
            continue

        if field.options and value not in field.options:
            errors.append(ValidationError(
                row_number, field.name,
                f"must be one of: {', '.join(map(str, field.options))}"
            ))
            continue

        if field.regex and not re.fullmatch(field.regex, str(value)):
            errors.append(ValidationError(
                row_number, field.name, "does not match required pattern"
            ))
            continue

        if field.include:
            output[field.name] = value

    return output, errors
