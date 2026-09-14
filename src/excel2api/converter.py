from .reader import read_file
from .schema import load_schema
from .validator import validate_and_convert


def convert_file(input_path: str, schema_path: str, sheet_name=None):
    rows = read_file(input_path, sheet_name=sheet_name)
    fields = load_schema(schema_path)

    records = []
    errors = []
    for row_number, row in enumerate(rows, start=2):
        record, row_errors = validate_and_convert(row, fields, row_number)
        if row_errors:
            errors.extend(row_errors)
        else:
            records.append(record)
    return records, errors
