"""
bfx list
────────
List all tables grouped by source database (tree view).
Empty tables are NOT shown in terminal — they are written to a file.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from bfx.core   import Session
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)



HELP = """
bfx list — List all tables in the session
==========================================

Shows every available table alias grouped by source database.
Skipped / empty tables are written to  skipped_tables.txt  in the
current directory (not shown in the terminal to keep output clean).

Usage:
  bfx --session <path> list [OPTIONS]

Options:
  --json           Output as JSON
  --show-skipped   Also print skipped tables in the terminal

Examples:
  bfx --session ./exports list
  bfx --session ./exports list --json
  bfx --session ./exports list --show-skipped

How to use an alias:
  After running list, use any alias shown in the tree with other commands:

    bfx --session ./exports view urls
    bfx --session ./exports head downloads --rows 20
    bfx --session ./exports search "gmail"
    bfx --session ./exports filter urls --col url__CATEGORY --value HTTPS
    bfx --session ./exports schema visits
    bfx --session ./exports info logins
"""


def run(
    session:       Session,
    as_json:       bool = False,
    show_skipped:  bool = False,
    skipped_file:  str  = "skipped_tables.txt",
) -> None:

    tables  = session.tables
    skipped = session.skipped

    if not tables and not skipped:
        print_warn("No tables found in this export folder.")
        print_info("Make sure --session points at a bfx export directory.")
        print_info("Run  bfx export --folder <path>  first.")
        return

    # ── JSON output ───────────────────────────────────────────────────────────
    if as_json:
        out = []
        for alias, tm in sorted(tables.items()):
            out.append({
                "alias":       alias,
                "table":       tm.table_name,
                "database":    tm.db_desc,
                "description": tm.table_desc,
                "rows":        tm.row_count,
                "columns":     len(tm.headers),
            })
        print(json.dumps(out, indent=2))
        return

    # ── Group tables by source database ───────────────────────────────────────
    by_db: dict[str, list] = defaultdict(list)
    for alias in sorted(tables):
        tm = tables[alias]
        by_db[tm.db_desc].append((alias, tm))

    # ── Tree output ───────────────────────────────────────────────────────────
    print_section(f"Session Tables  ({len(tables)} loaded, {len(skipped)} skipped)")
    print()

    total_rows = 0
    for db_desc, entries in sorted(by_db.items()):
        # Database header
        print(style(f"  {db_desc}", BOLD, WHITE))

        for i, (alias, tm) in enumerate(sorted(entries, key=lambda x: x[0])):
            is_last  = (i == len(entries) - 1)
            branch   = "  └─" if is_last else "  ├─"
            rows_str = f"{tm.row_count:>7,} rows"
            cols_str = f"{len(tm.headers)} cols"
            desc     = tm.table_desc if tm.table_desc and tm.table_desc != tm.table_name else ""

            # Alias in green, then counts dimmed, then description
            alias_col = style(f"{alias:<35}", GREEN, BOLD)
            meta_col  = style(f"{rows_str}  {cols_str}", DIM)
            desc_col  = style(f"  {desc}", DIM) if desc else ""

            print(f"  {branch} {alias_col}  {meta_col}{desc_col}")
            total_rows += tm.row_count

        print()

    print(style(f"  Total: {len(tables)} tables  |  {total_rows:,} rows across all tables", DIM))

    # ── Skipped tables — write to file, not terminal ──────────────────────────
    if skipped:
        _write_skipped_file(skipped, skipped_file)
        print()
        print(style(
            f"  {len(skipped)} empty/unreadable table(s) not shown above.",
            DIM
        ))
        print(style(
            f"  Full list written to: {skipped_file}",
            DIM
        ))
        if show_skipped:
            print()
            print(style("  Skipped tables:", BOLD))
            for tm in skipped:
                print(f"    - {tm.alias:<40}  [{tm.skip_reason}]")

    # ── Usage hint ────────────────────────────────────────────────────────────
    print()
    print(style("  Usage examples:", BOLD))
    print(style("    bfx --session <path> view <alias>", DIM))
    print(style("    bfx --session <path> head <alias> --rows 20", DIM))
    print(style("    bfx --session <path> search \"keyword\"", DIM))
    print(style("    bfx --session <path> filter <alias> --col <column> --value <value>", DIM))


def _write_skipped_file(skipped: list, path: str) -> None:
    """Write skipped tables to a plain-text file."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("BFX — Skipped / Empty Tables\n")
            f.write("=" * 60 + "\n")
            f.write("These tables were excluded from the terminal output\n")
            f.write("because they contained no data rows.\n\n")
            f.write(f"{'Alias':<40}  {'Reason':<30}  Source Table\n")
            f.write("-" * 100 + "\n")
            for tm in sorted(skipped, key=lambda x: x.alias):
                f.write(f"{tm.alias:<40}  {tm.skip_reason:<30}  {tm.table_name} in {tm.db_desc}\n")
    except Exception:
        pass   # Non-fatal — don't crash the main output
