import json
from pathlib import Path
import time

from .api import APIClient, APIResult
from .converter import convert_file
from .reader import read_file
from .schema import load_config


SUPPORTED_OPERATIONS = {"CREATE", "UPDATE", "PATCH", "DELETE", "UPSERT"}


def _save_checkpoint(path: str | Path, completed_rows: set[int]):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"completed_rows": sorted(completed_rows)}, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_checkpoint(path: str | Path) -> set[int]:
    path = Path(path)
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(row) for row in data.get("completed_rows", [])}


def sync_file(
    input_path: str,
    schema_path: str,
    api_url: str,
    operation_field: str = "operation",
    identifier_field: str = "id",
    token: str | None = None,
    dry_run: bool = False,
    timeout: int = 30,
    retries: int = 0,
    retry_create: bool = False,
    headers: dict[str, str] | None = None,
    rate_limit: float = 0.0,
    batch_size: int = 0,
    checkpoint: str | None = None,
    resume: bool = False,
    stop_on_error: bool = False,
    response_mapping: dict[str, str] | None = None,
    endpoints: dict[str, object] | None = None,
    sheet_name: str | int | None = None,
    record_overrides: dict[int, dict] | None = None,
):
    records, errors = convert_file(input_path, schema_path, sheet_name=sheet_name)
    if errors:
        return [], errors

    rows = read_file(input_path, sheet_name=sheet_name)
    record_overrides = record_overrides or {}
    if record_overrides:
        # Re-validate with dependency-provided values before API execution.
        from .schema import load_schema
        from .validator import validate_and_convert
        fields = load_schema(schema_path)
        records = []
        errors = []
        for row_number, raw_row in enumerate(rows, start=2):
            merged = dict(raw_row)
            for field_name, value in record_overrides.get(row_number, {}).items():
                for field in fields:
                    if field.name == field_name:
                        merged[field.column] = value
                        break
            record, row_errors = validate_and_convert(merged, fields, row_number)
            if row_errors:
                errors.extend(row_errors)
            else:
                records.append(record)
        if errors:
            return [], errors

    client = APIClient(
        api_url,
        token=token,
        timeout=timeout,
        retries=retries,
        retry_create=retry_create,
        headers=headers,
    )
    results = []
    completed_rows = _load_checkpoint(checkpoint) if (resume and checkpoint) else set()
    processed_since_checkpoint = 0

    for index, (row, record) in enumerate(zip(rows, records), start=2):
        if index in completed_rows:
            continue

        operation = str(row.get(operation_field) or "CREATE").upper()
        identifier = row.get(identifier_field)

        if operation not in SUPPORTED_OPERATIONS:
            result = APIResult(row=index, operation=operation, success=False,
                               error=f"unsupported operation: {operation}", record=record)
            results.append(result)
            if stop_on_error:
                break
            continue

        if dry_run:
            result = APIResult(row=index, operation=operation, success=True,
                               response={"dry_run": True, "record": record, "id": identifier}, record=record)
        else:
            try:
                if operation == "UPSERT":
                    if identifier is None:
                        raise ValueError("UPSERT requires an identifier")
                    response = client.execute("PATCH", record, identifier, endpoints=endpoints)
                else:
                    response = client.execute(operation, record, identifier, endpoints=endpoints)

                try:
                    response_body = response.json()
                except ValueError:
                    response_body = response.text

                result = APIResult(
                    row=index,
                    operation=operation,
                    success=response.ok,
                    status_code=response.status_code,
                    response=response_body,
                    error=None if response.ok else f"HTTP {response.status_code}",
                    record=record,
                )
            except Exception as exc:
                result = APIResult(row=index, operation=operation, success=False, error=str(exc), record=record)

        results.append(result)
        processed_since_checkpoint += 1

        if result.success:
            completed_rows.add(index)

        if checkpoint and (processed_since_checkpoint >= batch_size if batch_size > 0 else True):
            _save_checkpoint(checkpoint, completed_rows)
            processed_since_checkpoint = 0

        if stop_on_error and not result.success:
            break

        if rate_limit > 0 and index < len(rows) + 1:
            time.sleep(rate_limit)

    if checkpoint:
        _save_checkpoint(checkpoint, completed_rows)

    return results, []
