"""Lifecycle helpers for temporary extractor RAW batches.

RAW files are an interchange/recovery layer: create -> process -> delete on
verified success. On failure they remain available for retry.
"""

import json
from pathlib import Path


def write_raw_batch(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_raw_batch(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def delete_processed_raw(path: Path) -> None:
    if path.exists():
        path.unlink()
