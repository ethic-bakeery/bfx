"""
bfx.core.exporter
─────────────────
Shared utility for exporting result sets to CSV or JSON from any command.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Optional


def export_csv(
    path: str,
    headers: List[str],
    rows: List[List[str]],
    note: str = "",
) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if note:
            w.writerow([f"# {note}"])
            w.writerow([])
        w.writerow(headers)
        w.writerows(rows)
    return dest


def export_json(
    path: str,
    headers: List[str],
    rows: List[List[str]],
) -> Path:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    records = [dict(zip(headers, row)) for row in rows]
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str, ensure_ascii=False)
    return dest


def rows_to_json_str(headers: List[str], rows: List[List[str]]) -> str:
    records = [dict(zip(headers, row)) for row in rows]
    return json.dumps(records, indent=2, default=str, ensure_ascii=False)
