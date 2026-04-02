"""
bfx export
──────────
Run the browser forensic SQLite exporter directly from bfx.
Extracts all browser databases into the CSV format that all other
bfx commands can then read with --session.
"""

from __future__ import annotations

import sys
from pathlib import Path
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)




HELP = """
bfx export — Extract browser SQLite databases to CSV
======================================================

Runs the forensic exporter on a browser profile folder or a single
SQLite database file. The output folder can then be used directly
with all other bfx commands via --session.

Usage:
  bfx export --folder <path> [OPTIONS]
  bfx export --file   <path> [OPTIONS]

Arguments (one required):
  --folder PATH     Browser profile folder (e.g. Chrome Default/ directory)
  --file   PATH     Single SQLite database file

Options:
  --output  PATH    Where to write CSV exports  (default: ./bfx_export)
  --tables  LIST    Comma-separated table names to export (default: all)
  --limit   N       Max rows per table — useful for quick previews
  --recursive       Also scan sub-folders (when using --folder)

Examples:
  # Export a full Chrome profile
  bfx export --folder "C:/Users/cryfo/AppData/Local/Google/Chrome/User Data/Default" --output ./exports

  # Export a folder you already copied (like your Desktop/Browser/)
  bfx export --folder "C:/Users/cryfo/Desktop/Browser" --output ./exports

  # Export just the History file
  bfx export --file "C:/Users/cryfo/Desktop/Browser/History" --output ./exports

  # Export only specific tables
  bfx export --folder ./Browser --tables urls,visits,downloads --output ./exports

  # Quick preview — first 500 rows per table
  bfx export --folder ./Browser --limit 500 --output ./preview

After exporting, point bfx at the output folder:
  bfx --session ./exports list
  bfx --session ./exports summary
"""


def run(
    folder:    str | None,
    file:      str | None,
    output:    str = "./bfx_export",
    tables:    str | None = None,
    limit:     int | None = None,
    recursive: bool = False,
) -> None:

    # Import the engine (lives inside the package now)
    try:
        from bfx.core.exporter_engine import BrowserForensicExporter
    except ImportError as e:
        print_error(f"Exporter engine not found: {e}")
        print_info("Make sure bfx is installed correctly (pip install -e .)")
        sys.exit(1)

    print_section("BFX Export — Browser Forensic SQLite Exporter")

    tables_filter = [t.strip() for t in tables.split(",")] if tables else None

    exporter = BrowserForensicExporter(output_dir=output)

    print_info(f"Output directory : {style(output, CYAN)}")
    if folder:
        print_info(f"Source folder    : {style(folder, CYAN)}")
        if recursive:
            print_info("Mode             : recursive (scanning sub-folders)")
    else:
        print_info(f"Source file      : {style(str(file), CYAN)}")
    if tables_filter:
        print_info(f"Table filter     : {', '.join(tables_filter)}")
    if limit:
        print_info(f"Row limit        : {limit:,} rows per table (preview mode)")
    print()

    try:
        if file:
            exporter.export_database(file, tables_filter, limit)
        else:
            exporter.export_folder(folder, recursive, tables_filter, limit)

        exporter.write_manifest()
        exporter.print_summary()

        print()
        print_ok(f"Export complete. Now run:")
        print_info(
            style(f"  bfx --session {output} list", CYAN)
        )
        print_info(
            style(f"  bfx --session {output} summary", CYAN)
        )

    except KeyboardInterrupt:
        print()
        print_info("Export interrupted by user.")
    except Exception as e:
        print_error(f"Export failed: {e}")
        sys.exit(1)
