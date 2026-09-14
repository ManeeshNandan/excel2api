# Excel2API

Schema-driven Excel/CSV validation, transformation and API synchronization.

Excel2API turns spreadsheet rows into validated JSON and can optionally execute REST API operations such as CREATE, UPDATE, PATCH and DELETE.

## Features

- Excel and CSV input
- Multi-sheet input
- YAML-driven field mapping
- Type conversion and validation
- Required, nullable, default, length, numeric, regex, email and phone constraints
- Transformations (`strip`, `uppercase`, `lowercase`)
- JSON generation
- REST API CREATE / UPDATE / PATCH / DELETE
- Configurable endpoint templates
- Dry-run mode
- Bearer-token and custom-header authentication
- Configurable request timeout
- Retry with exponential backoff for transient HTTP failures
- Optional retry for CREATE requests
- Rate limiting
- Batch processing
- Resumable synchronization with checkpoints
- Stop-on-error control
- JSON and Excel sync reports
- Validation error Excel reports
- API response field mapping
- Dependency-aware multi-sheet synchronization
- Cross-sheet ID/reference resolution
- Circular dependency detection
- Control fields such as ID and Operation can stay in the spreadsheet without being sent to the API
- Configuration-file driven jobs
- `doctor` command for configuration validation

## Install

```bash
pip install excel2api
```

For development:

```bash
pip install -e ".[dev]"
```

## Validate

```bash
excel2api validate examples/patients.xlsx --schema examples/patient.yaml
```

## Convert

```bash
excel2api convert examples/patients.xlsx \
  --schema examples/patient.yaml \
  --output patients.json
```

## CRUD / API sync

The Excel file can contain `ID` and `Operation` columns:

```text
ID | Operation | Patient Name | ...
101 | UPDATE   | John Doe
102 | DELETE   | Jane Smith
    | CREATE   | Rahul Kumar
103 | PATCH    | Anita Thomas
```

`ID` and `Operation` are control fields in the CRUD schema, so they are used to decide what API call to make but are not included in the JSON payload sent to the API.

### Dry run

Always test a spreadsheet with dry-run before making changes to a real API:

```bash
excel2api sync examples/patients-crud.xlsx \
  --schema examples/patient-crud.yaml \
  --api https://example.com/api/patients \
  --dry-run
```

### Execute

```bash
excel2api sync examples/patients-crud.xlsx \
  --schema examples/patient-crud.yaml \
  --api https://example.com/api/patients \
  --token "$API_TOKEN"
```

### Timeout, retries and report

```bash
excel2api sync examples/patients-crud.xlsx \
  --schema examples/patient-crud.yaml \
  --api https://example.com/api/patients \
  --timeout 30 \
  --retries 3 \
  --report sync-report.json
```

By default, retries apply to idempotent operations (`PUT`, `PATCH`, `DELETE`) and transient responses such as `408`, `429`, `500`, `502`, `503` and `504`. CREATE (`POST`) is not retried by default because repeating a POST can create duplicate resources.

If the target API supports idempotent POSTs, CREATE retries can be explicitly enabled:

```bash
excel2api sync examples/patients-crud.xlsx \
  --schema examples/patient-crud.yaml \
  --api https://example.com/api/patients \
  --retries 3 \
  --retry-create
```

## Schema

A normal field is mapped and included in the API payload:

```yaml
patient_name:
  column: Patient Name
  type: string
  required: true
  min_length: 3
  transform: [strip]
```

A control field can be excluded from the generated API payload:

```yaml
id:
  column: ID
  type: integer
  nullable: true
  include: false
```

## Supported operations

- CREATE → POST `/resource`
- UPDATE → PUT `/resource/{id}`
- PATCH → PATCH `/resource/{id}`
- DELETE → DELETE `/resource/{id}`

## Architecture

```text
Excel / CSV
    ↓
Reader
    ↓
Schema Mapping
    ↓
Validation + Type Conversion
    ↓
Validated Records
    ↓
JSON Output       REST API Sync
                       ↓
                 API Client
                       ↓
                Result / Report
```

CRUD execution is intentionally separate from validation/conversion so the same core engine can be used for safe JSON generation without modifying remote data.

## Multi-sheet dependencies

Sheets can depend on other sheets. A successful API response can provide a value such as a newly created database ID to a dependent sheet.

```yaml
sheets:
  Doctors:
    schema: examples/doctor-dependency.yaml
    endpoint: /doctors
    response:
      mapping:
        api_id: id

  Patients:
    schema: examples/patient-dependency.yaml
    endpoint: /patients
    references:
      - target_field: doctor_id
        source_sheet: Doctors
        source_key: doctor_code
        target_key: doctor_code
        source_value: api_id
```

Excel2API executes `Doctors` first, indexes successful API IDs by `doctor_code`, and injects the matching ID into `Patients.doctor_id` before validation and API execution. Circular dependencies are rejected.

## Resumable synchronization

Large imports can be resumed without repeating successful rows:

```bash
excel2api sync patients.xlsx \
  --schema patient.yaml \
  --api https://example.com/api/patients \
  --checkpoint sync.checkpoint.json \
  --batch-size 50
```

Resume after an interruption:

```bash
excel2api sync patients.xlsx \
  --schema patient.yaml \
  --api https://example.com/api/patients \
  --checkpoint sync.checkpoint.json \
  --resume
```

## Custom API headers

```bash
excel2api sync patients.xlsx \
  --schema patient.yaml \
  --api https://example.com/api/patients \
  --header "X-API-Key=YOUR_KEY"
```

Multiple headers can be supplied. Bearer tokens can also be provided through `EXCEL2API_TOKEN` or another environment variable configured in YAML.

## Rate limiting and stop-on-error

```bash
excel2api sync patients.xlsx \
  --schema patient.yaml \
  --api https://example.com/api/patients \
  --rate-limit 0.2 \
  --batch-size 100 \
  --stop-on-error
```

## API response mapping

A schema can define response fields to extract into the sync report:

```yaml
response:
  mapping:
    api_id: id
    api_status: status
    api_message: message
```

Generate an Excel sync report:

```bash
excel2api sync examples/patients-crud.xlsx \
  --schema examples/patient-response.yaml \
  --api https://example.com/api/patients \
  --excel-report sync-results.xlsx
```

Validation failures can also be exported:

```bash
excel2api sync patients.xlsx \
  --schema patient.yaml \
  --api https://example.com/api/patients \
  --error-report validation-errors.xlsx
```

## Configuration file

For repeatable jobs, API settings and sync behavior can be stored in YAML:

```yaml
input: examples/patients-crud.xlsx
schema: examples/patient-response.yaml

api:
  base_url: https://example.com/api/patients
  auth:
    type: bearer
    token_env: PATIENT_API_TOKEN
  timeout: 30
  retries: 3
  rate_limit: 0.2
  headers:
    X-Client: excel2api

sync:
  operation_field: operation
  identifier_field: id
  batch_size: 100
  checkpoint: sync.checkpoint.json
  dry_run: true
  report: sync-report.json
  excel_report: sync-results.xlsx
```

Run the complete job with:

```bash
excel2api sync --config examples/excel2api.yaml
```

CLI options override values from the configuration file. Keep secrets out of YAML whenever possible; use `token_env` to read bearer tokens from environment variables.

## Endpoint templates

Use configurable endpoint templates when your API does not follow the default REST paths:

```yaml
api:
  base_url: https://example.com/api
  endpoints:
    CREATE:
      method: POST
      path: /patients
    UPDATE:
      method: PUT
      path: /patients/{id}
    PATCH:
      method: PATCH
      path: /patients/{id}
    DELETE:
      method: DELETE
      path: /patients/{id}
```

Endpoint paths may use `{id}`, `{identifier}`, or fields from the API payload, such as `{department}`.

## CLI commands

```text
excel2api convert
excel2api validate
excel2api sync
excel2api doctor
```

Check the installed version:

```bash
excel2api --version
```

## Development

Run tests from the repository root:

```bash
PYTHONPATH=src python -m pytest -q
```

Run linting:

```bash
ruff check src tests
```

Build the package:

```bash
python -m pip install build
python -m build
```

## Release

Excel2API uses GitHub Actions for CI and PyPI publishing. Releases are published from version tags such as `v1.0.0` after configuring PyPI Trusted Publishing for the repository.

## Roadmap

- UPSERT with explicit existence checking and POST/PUT selection
- API-key authentication as a first-class schema option
- Idempotency-key support
- Local mock API for end-to-end testing
- Additional authentication mechanisms
- Improved mapping expressions for nested API responses
