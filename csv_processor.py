import csv
import os
from typing import Callable, List, Optional
from models import CSVPreview, FilterConfig, ProcessResult


class CSVAnalyzer:
    CANDIDATE_DELIMITERS = [",", ";", "\t", "|"]
    SAMPLE_SIZE = 65536
    CHUNK_SIZE = 1024 * 1024

    @classmethod
    def detect_encoding(cls, file_path: str) -> str:
        with open(file_path, "rb") as f:
            sample = f.read(cls.SAMPLE_SIZE)
        if sample.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        try:
            sample.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "latin1"

    @classmethod
    def detect_delimiter(cls, file_path: str, encoding: str) -> str:
        try:
            with open(file_path, "r", newline="", encoding=encoding, errors="replace") as f:
                sample = f.read(cls.SAMPLE_SIZE)
            dialect = csv.Sniffer().sniff(sample, delimiters="".join(cls.CANDIDATE_DELIMITERS))
            if dialect.delimiter in cls.CANDIDATE_DELIMITERS:
                return dialect.delimiter
        except Exception:
            pass
        return ","

    @classmethod
    def count_data_lines(cls, file_path: str) -> int:
        total_newlines = 0
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(cls.CHUNK_SIZE), b""):
                total_newlines += chunk.count(b"\n")
        return max(total_newlines - 1, 0)

    @classmethod
    def load_preview(cls, file_path: str, delimiter: str, encoding: str, max_rows: int = 20) -> CSVPreview:
        with open(file_path, "r", newline="", encoding=encoding) as f:
            reader = csv.reader(f, delimiter=delimiter)
            header = next(reader)
            rows: List[List[str]] = []
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(row)
        return CSVPreview(columns=header, rows=rows)


class CSVReducer:
    def __init__(self, batch_notification_interval: int = 20_000):
        self.batch_notification_interval = batch_notification_interval

    def process(
        self,
        input_path: str,
        output_path: str,
        config: FilterConfig,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ProcessResult:
        rows_processed = 0
        rows_written = 0
        original_size = os.path.getsize(input_path)

        lo = (config.start_row - 1) if config.exclude_rows and config.start_row is not None else None
        hi = (config.end_row - 1) if config.exclude_rows and config.end_row is not None else None

        with open(input_path, "r", newline="", encoding=config.encoding) as fin, \
             open(output_path, "w", newline="", encoding=config.encoding) as fout:

            reader = csv.reader(fin, delimiter=config.delimiter)
            writer = csv.writer(fout, delimiter=config.delimiter)

            header = next(reader)
            writer.writerow([header[i] for i in config.keep_column_indices if i < len(header)])

            for i, row in enumerate(reader):
                rows_processed += 1
                if config.exclude_rows and lo is not None and hi is not None and lo <= i <= hi:
                    continue

                writer.writerow([row[j] for j in config.keep_column_indices if j < len(row)])
                rows_written += 1

                if progress_callback and rows_processed % self.batch_notification_interval == 0:
                    progress_callback(rows_processed, rows_written)

        final_size = os.path.getsize(output_path)
        return ProcessResult(
            rows_processed=rows_processed,
            rows_written=rows_written,
            original_size=original_size,
            final_size=final_size,
            output_path=output_path,
        )
