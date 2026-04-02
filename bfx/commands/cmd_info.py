"""
bfx info
────────
Show forensic metadata for a specific table: source DB path, MD5 hash,
export timestamp, column list, and row counts.
"""

from __future__ import annotations
import json
from bfx.core import Session
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)


HELP = """
bfx info — Show forensic metadata for a table
==============================================

Displays provenance information for a specific table export:
chain-of-custody data, column inventory, and row statistics.

Usage:
  bfx --session <path> info <alias> [OPTIONS]

Arguments:
  alias           Table alias (see: bfx list)

Options:
  --json          Output as JSON

Examples:
  bfx --session ./exports info urls
  bfx --session ./exports info logins --json
"""


def run(session: Session, alias: str, as_json: bool = False) -> None:

    try:
        tm = session.get(alias)
    except KeyError as e:
        print_error(str(e))
        return

    if as_json:
        out = {
            "alias":        tm.alias,
            "table_name":   tm.table_name,
            "table_desc":   tm.table_desc,
            "db_name":      tm.db_name,
            "db_desc":      tm.db_desc,
            "row_count":    tm.row_count,
            "total_rows_in_source": tm.total_rows,
            "export_timestamp": tm.export_ts,
            "md5_source_db": tm.md5,
            "csv_path":     str(tm.csv_path),
            "columns":      tm.headers,
            "column_count": len(tm.headers),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print_section(f"Table Info — {tm.alias}")

    _row("Alias",                style(tm.alias,       GREEN, BOLD))
    _row("Table name",           tm.table_name)
    _row("Description",          tm.table_desc or "—")
    print()
    _row("Source database",      tm.db_name)
    _row("DB description",       tm.db_desc)
    print()
    _row("Rows (this export)",   style(f"{tm.row_count:,}", CYAN))
    _row("Rows in source DB",    style(f"{tm.total_rows:,}", DIM))
    _row("Columns",              str(len(tm.headers)))
    print()
    _row("Export timestamp",     style(tm.export_ts, CYAN))
    _row("MD5 (source DB)",      style(tm.md5, WHITE))
    _row("CSV file",             str(tm.csv_path))
    print()

    print(style("  Columns:", WHITE, BOLD))
    for i, h in enumerate(tm.headers, 1):
        is_enriched = h.endswith(("__HUMAN", "__FORMAT", "__DOMAIN", "__CATEGORY"))
        tag  = style(" [enriched]", CYAN) if is_enriched else ""
        name = style(h, WHITE) if not is_enriched else style(h, DIM)
        print(f"    {i:>3}.  {name}{tag}")


def _row(label: str, value: str) -> None:
    print(f"  {style(label + ':', DIM):<28} {value}")
