from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FilterConfig:
    keep_column_indices: List[int]
    delimiter: str = ","
    encoding: str = "utf-8"
    exclude_rows: bool = False
    start_row: Optional[int] = None
    end_row: Optional[int] = None


@dataclass
class ProcessResult:
    rows_processed: int
    rows_written: int
    original_size: int
    final_size: int
    output_path: str

    @property
    def reduction_percentage(self) -> float:
        if self.original_size <= 0:
            return 0.0
        return (1.0 - (self.final_size / self.original_size)) * 100.0


@dataclass
class CSVPreview:
    columns: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
