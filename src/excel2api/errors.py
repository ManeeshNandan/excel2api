from dataclasses import dataclass


@dataclass
class ValidationError:
    row: int
    field: str
    message: str
    sheet: str | None = None

    def as_dict(self) -> dict:
        return {
            "row": self.row,
            "field": self.field,
            "message": self.message,
            "sheet": self.sheet,
        }
