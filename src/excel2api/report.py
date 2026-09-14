from pathlib import Path
from typing import Any

from openpyxl import Workbook


def extract_path(data: Any, path: str, default=None):
    """Extract a dotted path from a JSON-like response."""
    if not path:
        return default
    current = data
    for part in path.split('.'):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def write_error_report(path: str | Path, errors: list[Any]):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Errors"
    sheet.append(["Sheet", "Row", "Field", "Message"])
    for error in errors:
        sheet.append([getattr(error, "sheet", ""), error.row, error.field, error.message])
    workbook.save(path)


def write_sync_report(path: str | Path, results: list[Any], response_mapping: dict[str, str] | None = None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sync Results"

    mapping = response_mapping or {}
    headers = ["Sheet", "Row", "Operation", "Success", "HTTP Status", "Error"] + list(mapping.keys())
    sheet.append(headers)

    for result in results:
        values = [getattr(result, "sheet", ""), result.row, result.operation, result.success, result.status_code, result.error]
        for output_name, response_path in mapping.items():
            values.append(extract_path(result.response, response_path, ""))
        sheet.append(values)

    workbook.save(path)
