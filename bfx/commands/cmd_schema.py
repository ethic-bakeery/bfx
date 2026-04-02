"""
bfx schema
──────────
Show the full column schema for a table: names, enrichment columns flagged,
and a sample of unique values for each column.
"""

from __future__ import annotations
import json
from collections import Counter
from typing import Optional
from bfx.core import Session
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)


HELP = """
bfx schema — Show column schema for a table
============================================

Displays all columns, whether they are original or bfx-enriched,
and a sample of the most common values in each column.

Usage:
  bfx --session <path> schema <alias> [OPTIONS]

Arguments:
  alias           Table alias (see: bfx list)

Options:
  --json          Output as JSON
  --samples N     Number of sample values per column (default: 5)

Examples:
  bfx --session ./exports schema urls
  bfx --session ./exports schema visits --samples 10
  bfx --session ./exports schema logins --json
"""


def run(
    session: Session,
    alias:   str,
    as_json: bool = False,
    samples: int  = 5,
) -> None:

    try:
        tm = session.get(alias)
    except KeyError as e:
        print_error(str(e))
        return

    headers, data = session.read_rows(alias)

    # Build per-column stats
    cols_info = []
    for i, h in enumerate(headers):
        vals = [row[i] for row in data if i < len(row) and row[i].strip()]
        counter   = Counter(vals)
        top       = [v for v, _ in counter.most_common(samples)]
        is_enrich = h.endswith(("__HUMAN", "__FORMAT", "__DOMAIN", "__CATEGORY"))
        cols_info.append({
            "column":    h,
            "kind":      "enriched" if is_enrich else "original",
            "non_empty": len(vals),
            "unique":    len(counter),
            "samples":   top,
        })

    if as_json:
        print(json.dumps(cols_info, indent=2, ensure_ascii=False))
        return

    print_section(
        f"Schema — {style(tm.alias, GREEN, BOLD)}  ·  {tm.table_desc or tm.table_name}"
    )
    print_info(f"Source DB  : {tm.db_desc}")
    print_info(f"Total rows : {tm.row_count:,}  (source DB had {tm.total_rows:,})")
    print_info(f"Exported   : {tm.export_ts}   MD5: {tm.md5}")
    print()

    tbl_headers = ["#", "Column", "Kind", "Non-empty", "Unique", f"Top {samples} values"]
    rows = []
    for i, col in enumerate(cols_info, 1):
        kind_label = (
            style("enriched", CYAN) if col["kind"] == "enriched"
            else style("original", DIM)
        )
        rows.append([
            str(i),
            style(col["column"], WHITE, BOLD),
            kind_label,
            f"{col['non_empty']:,}",
            f"{col['unique']:,}",
            "  |  ".join(col["samples"][:samples]) or style("(all empty)", DIM),
        ])

    renderer = TableRenderer(tbl_headers, rows)
    for line in renderer.render():
        print(line)
