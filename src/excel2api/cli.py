import json
import os
from pathlib import Path
import typer

from .converter import convert_file
from .config import load_sync_config
from .sync import sync_file
from .schema import load_config
from .report import write_error_report, write_sync_report
from .dependencies import dependency_order, resolve_overrides
from .doctor import validate_sync_config
from . import __version__

app = typer.Typer(help="Convert Excel/CSV into validated API-ready data.")


@app.command()
def doctor(
    config: Path = typer.Argument(..., exists=True),
):
    """Validate a sync configuration before running a migration."""
    try:
        problems = validate_sync_config(config)
    except Exception as exc:
        typer.echo(f"ERROR: {exc}")
        raise typer.Exit(code=2)
    if problems:
        typer.echo("Configuration check failed:")
        for problem in problems:
            typer.echo(f"- {problem}")
        raise typer.Exit(code=2)
    typer.echo(f"Excel2API {__version__}: configuration OK")


@app.callback(invoke_without_command=True)
def main(version: bool = typer.Option(False, "--version", help="Show version and exit.")):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def convert(
    input_file: Path = typer.Argument(..., exists=True),
    schema: Path = typer.Option(..., "--schema", "-s", exists=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
):
    """Validate and convert Excel/CSV data to JSON."""
    records, errors = convert_file(str(input_file), str(schema))
    if output:
        output.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
        typer.echo(f"Output written to {output}")
    else:
        typer.echo(json.dumps(records, indent=2, default=str))
    typer.echo(f"Valid records: {len(records)}")
    typer.echo(f"Errors: {len(errors)}")
    if errors:
        for error in errors:
            typer.echo(f"Row {error.row} | {error.field} | {error.message}")
        raise typer.Exit(code=1)


@app.command()
def validate(
    input_file: Path = typer.Argument(..., exists=True),
    schema: Path = typer.Option(..., "--schema", "-s", exists=True),
):
    """Validate Excel/CSV data without writing JSON output."""
    records, errors = convert_file(str(input_file), str(schema))
    typer.echo(f"Valid records: {len(records)}")
    typer.echo(f"Errors: {len(errors)}")
    for error in errors:
        typer.echo(f"Row {error.row} | {error.field} | {error.message}")
    if errors:
        raise typer.Exit(code=1)


def _parse_headers(items: list[str], configured: dict[str, str]) -> dict[str, str]:
    headers = dict(configured or {})
    for item in items:
        if "=" not in item:
            raise typer.BadParameter("Header must use NAME=VALUE format", param_hint="--header")
        name, value = item.split("=", 1)
        headers[name.strip()] = value
    return headers


def _auth_token(cfg_api: dict, token: str | None) -> str | None:
    if token is not None:
        return token
    auth = cfg_api.get("auth", {}) or {}
    auth_type = str(auth.get("type", "none")).lower()
    if auth_type == "bearer":
        token_env = auth.get("token_env", "EXCEL2API_TOKEN")
        return os.getenv(token_env) or auth.get("token")
    return os.getenv("EXCEL2API_TOKEN")


@app.command()
def sync(
    input_file: Path | None = typer.Argument(None, exists=True),
    schema: Path | None = typer.Option(None, "--schema", "-s", exists=True),
    api: str | None = typer.Option(None, "--api"),
    config: Path | None = typer.Option(None, "--config", "-c", exists=True),
    operation_field: str | None = typer.Option(None, "--operation-field"),
    identifier_field: str | None = typer.Option(None, "--id-field"),
    token: str | None = typer.Option(None, "--token"),
    dry_run: bool | None = typer.Option(None, "--dry-run/--no-dry-run"),
    timeout: int | None = typer.Option(None, "--timeout", min=1),
    retries: int | None = typer.Option(None, "--retries", min=0, max=10),
    retry_create: bool | None = typer.Option(None, "--retry-create/--no-retry-create"),
    report: Path | None = typer.Option(None, "--report"),
    header: list[str] = typer.Option([], "--header"),
    rate_limit: float | None = typer.Option(None, "--rate-limit", min=0.0),
    batch_size: int | None = typer.Option(None, "--batch-size", min=0),
    checkpoint: Path | None = typer.Option(None, "--checkpoint"),
    resume: bool | None = typer.Option(None, "--resume/--no-resume"),
    stop_on_error: bool | None = typer.Option(None, "--stop-on-error/--continue-on-error"),
    excel_report: Path | None = typer.Option(None, "--excel-report"),
    error_report: Path | None = typer.Option(None, "--error-report"),
):
    """Execute one or multiple Excel sheets against API endpoints."""
    cfg = load_sync_config(str(config)) if config else {}
    cfg_api = cfg.get("api", {}) or {}
    cfg_sync = cfg.get("sync", {}) or {}

    input_file = input_file or (Path(cfg["input"]) if cfg.get("input") else None)
    schema = schema or (Path(cfg["schema"]) if cfg.get("schema") else None)
    api = api or cfg_api.get("base_url")
    if not input_file or not input_file.exists():
        raise typer.BadParameter("Input file is required (argument or config.input)")
    if not api and not cfg.get("sheets"):
        raise typer.BadParameter("API URL is required (--api or config.api.base_url)")
    if not schema and not cfg.get("sheets"):
        raise typer.BadParameter("Schema file is required (--schema or config.schema)")

    operation_field = operation_field or cfg_sync.get("operation_field", "operation")
    identifier_field = identifier_field or cfg_sync.get("identifier_field", "id")
    timeout = timeout if timeout is not None else int(cfg_api.get("timeout", 30))
    retries = retries if retries is not None else int(cfg_api.get("retries", 0))
    retry_create = retry_create if retry_create is not None else bool(cfg_api.get("retry_create", False))
    rate_limit = rate_limit if rate_limit is not None else float(cfg_api.get("rate_limit", 0.0))
    batch_size = batch_size if batch_size is not None else int(cfg_sync.get("batch_size", 0))
    resume = resume if resume is not None else bool(cfg_sync.get("resume", False))
    stop_on_error = stop_on_error if stop_on_error is not None else bool(cfg_sync.get("stop_on_error", False))
    dry_run = dry_run if dry_run is not None else bool(cfg_sync.get("dry_run", False))
    checkpoint = checkpoint or (Path(cfg_sync["checkpoint"]) if cfg_sync.get("checkpoint") else None)
    report = report or (Path(cfg_sync["report"]) if cfg_sync.get("report") else None)
    excel_report = excel_report or (Path(cfg_sync["excel_report"]) if cfg_sync.get("excel_report") else None)
    error_report = error_report or (Path(cfg_sync["error_report"]) if cfg_sync.get("error_report") else None)
    headers = _parse_headers(header, cfg_api.get("headers", {}))
    token = _auth_token(cfg_api, token)

    sheets = cfg.get("sheets") or {}
    jobs = []
    if sheets:
        for sheet_name, sheet_cfg in sheets.items():
            sheet_cfg = sheet_cfg or {}
            sheet_schema = Path(sheet_cfg["schema"])
            sheet_api = str(api or cfg_api.get("base_url", "")).rstrip("/")
            endpoint = sheet_cfg.get("endpoint")
            if endpoint:
                sheet_api += "/" + str(endpoint).lstrip("/")
            jobs.append((sheet_name, sheet_schema, sheet_api, sheet_cfg))
    else:
        jobs.append((None, schema, api, {}))

    # Resolve multi-sheet dependencies before execution. Sheets without references
    # retain their configured order; dependencies are topologically sorted.
    if sheets:
        ordered_names = dependency_order(sheets)
        jobs_by_name = {job[0]: job for job in jobs}
        jobs = [jobs_by_name[name] for name in ordered_names]
        for name, _, _, cfg_item in jobs:
            cfg_item["_all_sheets"] = sheets

    all_results = []
    all_errors = []
    results_by_sheet = {}
    for sheet_name, job_schema, job_api, sheet_cfg in jobs:
        if not job_schema.exists():
            raise typer.BadParameter(f"Schema file not found for sheet '{sheet_name}': {job_schema}")
        job_sync = sheet_cfg.get("sync", {}) or {}
        job_endpoints = sheet_cfg.get("endpoints", cfg_api.get("endpoints", {})) or {}
        job_operation = sheet_cfg.get("operation_field", job_sync.get("operation_field", operation_field))
        job_identifier = sheet_cfg.get("identifier_field", job_sync.get("identifier_field", identifier_field))
        job_response = sheet_cfg.get("response", cfg.get("response", {})) or {}
        job_mapping = job_response.get("mapping", {}) or {}
        job_checkpoint = sheet_cfg.get("checkpoint")
        if job_checkpoint is None:
            job_checkpoint = str(checkpoint) if checkpoint and not sheets else None
        job_resume = bool(sheet_cfg.get("resume", resume))
        job_batch = int(sheet_cfg.get("batch_size", batch_size))

        overrides = {}
        if sheet_name:
            overrides = resolve_overrides(str(input_file), sheet_name, sheet_cfg, results_by_sheet)

        results, errors = sync_file(
            str(input_file), str(job_schema), job_api,
            operation_field=job_operation, identifier_field=job_identifier,
            token=token, dry_run=bool(sheet_cfg.get("dry_run", dry_run)),
            timeout=int(sheet_cfg.get("timeout", timeout)), retries=int(sheet_cfg.get("retries", retries)),
            retry_create=bool(sheet_cfg.get("retry_create", retry_create)), headers=headers,
            rate_limit=float(sheet_cfg.get("rate_limit", rate_limit)), batch_size=job_batch,
            checkpoint=job_checkpoint, resume=job_resume,
            stop_on_error=bool(sheet_cfg.get("stop_on_error", stop_on_error)),
            response_mapping=job_mapping, endpoints=job_endpoints, sheet_name=sheet_name,
            record_overrides=overrides,
        )
        for r in results:
            r.sheet = sheet_name
        for e in errors:
            e.sheet = sheet_name
        all_results.extend(results)
        all_errors.extend(errors)
        if sheet_name:
            results_by_sheet[sheet_name] = results
        typer.echo(f"Sheet: {sheet_name or 'default'} | processed: {len(results)} | validation errors: {len(errors)}")

    if all_errors:
        if error_report:
            write_error_report(error_report, all_errors)
            typer.echo(f"Error report written to {error_report}")
        for error in all_errors:
            typer.echo(f"Sheet {getattr(error, 'sheet', None)} | Row {error.row} | {error.field} | {error.message}")
        raise typer.Exit(code=1)

    counts, failures = {}, 0
    for result in all_results:
        counts[result.operation] = counts.get(result.operation, 0) + 1
        failures += int(not result.success)
        status = "OK" if result.success else "FAILED"
        detail = f"HTTP {result.status_code}" if result.status_code is not None else result.error or "DRY RUN"
        typer.echo(f"Sheet {getattr(result, 'sheet', None) or 'default'} | Row {result.row} | {result.operation} | {status} | {detail}")

    typer.echo("\nSummary")
    typer.echo(f"Total: {len(all_results)}")
    for operation, count in sorted(counts.items()):
        typer.echo(f"{operation}: {count}")
    typer.echo(f"Failed: {failures}")

    if report:
        data = [{"sheet": getattr(r, "sheet", None), "row": r.row, "operation": r.operation,
                 "success": r.success, "status_code": r.status_code, "response": r.response,
                 "error": r.error} for r in all_results]
        report.write_text(json.dumps({"results": data, "summary": {"total": len(data), "failed": failures}}, indent=2, default=str), encoding="utf-8")
        typer.echo(f"Report written to {report}")
    if excel_report:
        # Response mappings can differ per sheet; use a generic combined report.
        write_sync_report(excel_report, all_results)
        typer.echo(f"Excel report written to {excel_report}")
    if failures:
        raise typer.Exit(code=1)
