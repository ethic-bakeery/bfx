"""
bfx head / bfx tail
───────────────────
Show the first or last N rows of a table — instant, no pagination.
"""

from __future__ import annotations

from typing import Optional

from bfx.core  import Session, export_csv, rows_to_json_str
from bfx.ui    import TableRenderer, print_section, print_error, print_ok, style
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)



HELP_HEAD = """
bfx head — Show the first N rows of a table
============================================

Usage:
  bfx --session <path> head <alias> [OPTIONS]

Arguments:
  alias           Table alias (see: bfx list)

Options:
  --rows N        Number of rows to show (default: 10)
  --json          Output as JSON
  --export FILE   Export result to FILE (.csv or .json)

Examples:
  bfx --session ./exports head urls
  bfx --session ./exports head visits --rows 25
  bfx --session ./exports head downloads --json
"""

HELP_TAIL = """
bfx tail — Show the last N rows of a table
===========================================

Usage:
  bfx --session <path> tail <alias> [OPTIONS]

Arguments:
  alias           Table alias (see: bfx list)

Options:
  --rows N        Number of rows to show (default: 10)
  --json          Output as JSON
  --export FILE   Export result to FILE (.csv or .json)

Examples:
  bfx --session ./exports tail visits
  bfx --session ./exports tail downloads --rows 5
"""


def run(
    session:   Session,
    alias:     str,
    rows:      int = 10,
    from_end:  bool = False,
    as_json:   bool = False,
    export:    Optional[str] = None,
) -> None:

    try:
        tm = session.get(alias)
    except KeyError as e:
        print_error(str(e))
        return

    headers, data = session.read_rows(alias, rows=rows, from_end=from_end)

    direction = "last" if from_end else "first"
    title = (
        f"  {style(direction + ' ' + str(len(data)) + ' rows', YELLOW, BOLD)}"
        f"  of  {style(tm.alias, GREEN)}  ·  {tm.table_desc or tm.table_name}"
    )

    if as_json:
        print(rows_to_json_str(headers, data))
        return

    if export:
        try:
            dest = export_csv(export, headers, data,
                              note=f"bfx {direction} {rows} — {tm.table_name}")
            print_ok(f"Exported {len(data):,} rows → {dest}")
        except Exception as e:
            print_error(f"Export failed: {e}")
        return

    renderer = TableRenderer(headers, data, title=title)
    for line in renderer.render():
        print(line)
