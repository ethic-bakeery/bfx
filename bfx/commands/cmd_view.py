"""
bfx view
────────
View a table with full pagination (like `less`).
Supports JSON output and CSV/JSON export of the full table.
"""

from __future__ import annotations
import json
from typing import Optional
from bfx.core  import Session, export_csv, export_json, rows_to_json_str
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)


HELP = """
bfx view — View a table with pagination
========================================

Displays the full contents of a table, paginated (SPACE=next, b=prev, q=quit).

Usage:
  bfx --session <path> view <alias> [OPTIONS]

Arguments:
  alias           Table alias (see: bfx list)

Options:
  --rows N        Show only the first N rows (skips pagination)
  --json          Print as JSON to stdout
  --export FILE   Export full table to FILE (.csv or .json)
  --no-color      Disable ANSI colours

Examples:
  bfx --session ./exports view urls
  bfx --session ./exports view downloads --rows 20
  bfx --session ./exports view urls --json | jq '.[].url'
  bfx --session ./exports view logins --export ./logins_review.csv
"""


def run(
    session:  Session,
    alias:    str,
    rows:     Optional[int] = None,
    as_json:  bool = False,
    export:   Optional[str] = None,
) -> None:

    try:
        tm = session.get(alias)
    except KeyError as e:
        print_error(str(e))
        return

    headers, data = session.read_rows(alias, rows=rows)

    # ── JSON stdout ───────────────────────────────────────────────────────────
    if as_json:
        print(rows_to_json_str(headers, data))
        return

    # ── Export ────────────────────────────────────────────────────────────────
    if export:
        _do_export(export, headers, data, tm.table_name)

    # ── Terminal table ────────────────────────────────────────────────────────
    title = (
        f"  {style(tm.alias, GREEN, BOLD)}  ·  {tm.table_desc or tm.table_name}"
        f"  ·  {tm.db_desc}"
    )
    renderer = TableRenderer(headers, data, title=title)
    Paginator(renderer.render()).display()

    if not export:
        print_info(
            f"Tip: add  {style('--export out.csv', CYAN)}  to save this table."
        )


def _do_export(path: str, headers, data, table_name: str) -> None:
    try:
        if path.endswith(".json"):
            dest = export_json(path, headers, data)
        else:
            dest = export_csv(path, headers, data, note=f"bfx export — {table_name}")
        print_ok(f"Exported {len(data):,} rows → {dest}")
    except Exception as e:
        print_error(f"Export failed: {e}")
