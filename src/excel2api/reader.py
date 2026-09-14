from pathlib import Path
import pandas as pd

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def _validate_path(path: str | Path) -> Path:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {path.suffix}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return path


def list_sheets(path: str | Path) -> list[str]:
    path = _validate_path(path)
    if path.suffix.lower() == ".csv":
        return ["CSV"]
    return list(pd.ExcelFile(path).sheet_names)


def read_file(path: str | Path, sheet_name: str | int | None = None) -> list[dict]:
    path = _validate_path(path)
    if path.suffix.lower() == ".csv":
        if sheet_name not in (None, "CSV"):
            raise ValueError("CSV files do not contain multiple sheets")
        frame = pd.read_csv(path)
    else:
        frame = pd.read_excel(path, sheet_name=sheet_name if sheet_name is not None else 0)

    frame = frame.where(pd.notna(frame), None)
    return frame.to_dict(orient="records")
