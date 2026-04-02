"""
bfx filter
──────────
Filter a table by column=value, range, or regex.
Supports multiple conditions (AND logic).
"""

from __future__ import annotations
import re
from typing import List, Optional, Tuple
from bfx.core  import Session, export_csv, rows_to_json_str
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)


HELP = """
bfx filter — Filter a table by column value
============================================

Filters rows where the specified column matches a value.
Multiple --col / --value pairs are AND-ed together.

Usage:
  bfx --session <path> filter <alias> --col COLUMN --value VALUE [OPTIONS]

Arguments:
  alias           Table alias (see: bfx list)

Options:
  --col COLUMN    Column name to filter on (repeatable)
  --value VALUE   Value to match (repeatable, paired with --col)
  --regex         Treat VALUE as a regular expression
  --case          Case-sensitive match
  --rows N        Max rows to display (default: all)
  --json          Output as JSON
  --export FILE   Export filtered rows to FILE (.csv or .json)

Examples:
  bfx --session ./exports filter urls --col url__CATEGORY --value HTTPS
  bfx --session ./exports filter visits --col transition --value 1
  bfx --session ./exports filter urls --col url --value gmail --regex
  bfx --session ./exports filter downloads --col url__CATEGORY --value HTTPS \\
                                           --export https_downloads.csv
"""


def run(
    session:        Session,
    alias:          str,
    conditions:     List[Tuple[str, str]],  # list of (col, value) pairs
    use_regex:      bool = False,
    case_sensitive: bool = False,
    rows:           Optional[int] = None,
    as_json:        bool = False,
    export:         Optional[str] = None,
) -> None:

    if not conditions:
        print_error("Provide at least one --col / --value pair.")
        print_info("Example:  bfx filter urls --col url__CATEGORY --value HTTPS")
        return

    try:
        tm = session.get(alias)
    except KeyError as e:
        print_error(str(e))
        return

    headers, data = session.read_rows(alias)
    hdr_lower = [h.lower() for h in headers]

    # Build compiled matchers
    matchers: List[Tuple[int, re.Pattern]] = []
    for col, val in conditions:
        if col.lower() not in hdr_lower:
            print_error(
                f"Column '{col}' not found in '{alias}'.\n"
                f"  Available columns: {', '.join(headers)}"
            )
            return
        idx   = hdr_lower.index(col.lower())
        flags = 0 if case_sensitive else re.IGNORECASE
        pat_str = val if use_regex else re.escape(val)
        try:
            pat = re.compile(pat_str, flags)
        except re.error as e:
            print_error(f"Invalid regex '{val}': {e}")
            return
        matchers.append((idx, pat))

    # Filter
    matched = []
    for row in data:
        if all(
            pat.search(str(row[idx]) if idx < len(row) else "")
            for idx, pat in matchers
        ):
            matched.append(row)

    if not matched:
        cond_str = "  AND  ".join(f"{c}={v}" for c, v in conditions)
        print_warn(f"No rows matched:  {cond_str}")
        print_info(f"Total rows in '{alias}': {len(data):,}")
        return

    display = matched[:rows] if rows else matched

    if as_json:
        print(rows_to_json_str(headers, display))
        return

    if export:
        try:
            cond_note = ", ".join(f"{c}={v}" for c, v in conditions)
            dest = export_csv(export, headers, display,
                              note=f"bfx filter — {tm.table_name}  [{cond_note}]")
            print_ok(f"Exported {len(display):,} rows → {dest}")
        except Exception as e:
            print_error(f"Export failed: {e}")
        return

    cond_display = "  AND  ".join(
        f"{style(c, CYAN)}={style(v, YELLOW)}" for c, v in conditions
    )
    title = (
        f"  {style(tm.alias, GREEN, BOLD)}  filter: {cond_display}"
        f"  ·  {len(matched):,} match(es)"
    )
    renderer = TableRenderer(headers, display, title=title)
    Paginator(renderer.render()).display()
