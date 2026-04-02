"""
bfx.cli
───────
Main entry point. Routes all commands. --session not required for `export`.
"""

from __future__ import annotations

import argparse
import os
import sys
from textwrap import dedent

from bfx import __version__
from bfx.core.session  import Session
from bfx.ui.terminal   import Theme, print_error, print_banner, style

from bfx.commands import (
    cmd_list, cmd_view, cmd_head_tail, cmd_search,
    cmd_filter, cmd_schema, cmd_summary, cmd_info, cmd_export,
)

# ── Help text ─────────────────────────────────────────────────────────────────

_TOP = dedent(f"""\
    Browser Forensic Explorer v{__version__}
    ────────────────────────────────────────
    Professional CLI for browser forensic artifact analysis.
    Zero external dependencies — pure Python 3.8+.

    TYPICAL WORKFLOW
      Step 1 — Extract browser databases:
        bfx export --folder "C:/Users/.../Chrome/Default" --output ./exports

      Step 2 — Explore the export:
        bfx --session ./exports list
        bfx --session ./exports summary
        bfx --session ./exports view urls
        bfx --session ./exports search "keyword"
        bfx --session ./exports head downloads --rows 20
        bfx --session ./exports filter urls --col url__CATEGORY --value HTTPS
        bfx --session ./exports schema visits
        bfx --session ./exports info logins
""")

_EPILOG = dedent("""\
    GLOBAL OPTIONS (place before the subcommand)
      --session PATH    Path to bfx export folder   [required for all except export]
      --no-color        Disable ANSI colour
      -v / --version    Print version and exit

    Run  bfx <command> --help  for full options of any command.
""")

# ── Formatter ─────────────────────────────────────────────────────────────────

class _Fmt(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=28, width=88)

# ── Parser ────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bfx",
        description=_TOP,
        epilog=_EPILOG,
        formatter_class=_Fmt,
    )
    p.add_argument("--session",  metavar="PATH",
                   help="Path to the bfx export folder")
    p.add_argument("--no-color", action="store_true",
                   help="Disable ANSI colour output")
    p.add_argument("-v", "--version", action="version", version=f"bfx {__version__}")

    sub = p.add_subparsers(dest="command", metavar="<command>")

    # export ──────────────────────────────────────────────────────────────────
    pe = sub.add_parser("export",
        help="Extract browser SQLite databases to CSV (run this first)",
        description=cmd_export.HELP, formatter_class=_Fmt)
    g = pe.add_mutually_exclusive_group(required=True)
    g.add_argument("--folder", metavar="PATH",
                   help="Browser profile folder to scan")
    g.add_argument("--file",   metavar="PATH",
                   help="Single SQLite database file")
    pe.add_argument("--output",    default="./bfx_export", metavar="PATH",
                    help="Output directory (default: ./bfx_export)")
    pe.add_argument("--tables",    metavar="LIST",
                    help="Comma-separated table names to export")
    pe.add_argument("--limit",     type=int, metavar="N",
                    help="Max rows per table (preview mode)")
    pe.add_argument("--recursive", action="store_true",
                    help="Scan sub-folders recursively")

    # list ────────────────────────────────────────────────────────────────────
    pl = sub.add_parser("list",
        help="List all available table aliases in the session",
        description=cmd_list.HELP, formatter_class=_Fmt)
    pl.add_argument("--json", action="store_true", help="Output as JSON")

    # view ────────────────────────────────────────────────────────────────────
    pv = sub.add_parser("view",
        help="View a table with pagination  (SPACE=next  B=prev  Q=quit)",
        description=cmd_view.HELP, formatter_class=_Fmt)
    pv.add_argument("alias", help="Table alias (see: bfx list)")
    pv.add_argument("--rows",   type=int, metavar="N",
                    help="Show only first N rows (skips pagination)")
    pv.add_argument("--json",   action="store_true", help="Output as JSON")
    pv.add_argument("--export", metavar="FILE",
                    help="Export full table to FILE (.csv or .json)")

    # head ────────────────────────────────────────────────────────────────────
    ph = sub.add_parser("head",
        help="Show first N rows of a table  (default 10)",
        description=cmd_head_tail.HELP_HEAD, formatter_class=_Fmt)
    ph.add_argument("alias", help="Table alias")
    ph.add_argument("--rows",   type=int, default=10, metavar="N")
    ph.add_argument("--json",   action="store_true")
    ph.add_argument("--export", metavar="FILE")

    # tail ────────────────────────────────────────────────────────────────────
    pt = sub.add_parser("tail",
        help="Show last N rows of a table  (default 10)",
        description=cmd_head_tail.HELP_TAIL, formatter_class=_Fmt)
    pt.add_argument("alias", help="Table alias")
    pt.add_argument("--rows",   type=int, default=10, metavar="N")
    pt.add_argument("--json",   action="store_true")
    pt.add_argument("--export", metavar="FILE")

    # search ──────────────────────────────────────────────────────────────────
    ps = sub.add_parser("search",
        help="Search a keyword across ALL tables simultaneously",
        description=cmd_search.HELP, formatter_class=_Fmt)
    ps.add_argument("keyword", help="Text to search (case-insensitive by default)")
    ps.add_argument("--table",  metavar="ALIAS",
                    help="Limit search to one specific table alias")
    ps.add_argument("--col",    metavar="COLUMN",
                    help="Search only within this column name")
    ps.add_argument("--case",   action="store_true",
                    help="Case-sensitive matching")
    ps.add_argument("--rows",   type=int, default=50, metavar="N",
                    help="Max matching rows to show per table (default: 50)")
    ps.add_argument("--json",   action="store_true")
    ps.add_argument("--export", metavar="FILE",
                    help="Export all hits to FILE (.csv or .json)")

    # filter ──────────────────────────────────────────────────────────────────
    pf = sub.add_parser("filter",
        help="Filter a table by column value (supports regex, multi-condition AND)",
        description=cmd_filter.HELP, formatter_class=_Fmt)
    pf.add_argument("alias", help="Table alias")
    pf.add_argument("--col",   action="append", dest="cols",   metavar="COLUMN",
                    help="Column to filter on (repeatable)")
    pf.add_argument("--value", action="append", dest="values", metavar="VALUE",
                    help="Value to match (repeatable, paired with --col)")
    pf.add_argument("--regex", action="store_true",
                    help="Treat VALUE as a regular expression")
    pf.add_argument("--case",  action="store_true",
                    help="Case-sensitive match")
    pf.add_argument("--rows",  type=int, metavar="N")
    pf.add_argument("--json",  action="store_true")
    pf.add_argument("--export", metavar="FILE")

    # schema ──────────────────────────────────────────────────────────────────
    psc = sub.add_parser("schema",
        help="Show column schema, types, and sample values for a table",
        description=cmd_schema.HELP, formatter_class=_Fmt)
    psc.add_argument("alias", help="Table alias")
    psc.add_argument("--json",    action="store_true")
    psc.add_argument("--samples", type=int, default=5, metavar="N",
                     help="Sample values per column (default: 5)")

    # summary ─────────────────────────────────────────────────────────────────
    psu = sub.add_parser("summary",
        help="Session-wide overview: date range, top domains, searches, downloads",
        description=cmd_summary.HELP, formatter_class=_Fmt)
    psu.add_argument("--json", action="store_true")

    # info ────────────────────────────────────────────────────────────────────
    pi = sub.add_parser("info",
        help="Show forensic metadata (MD5, source path, timestamps) for a table",
        description=cmd_info.HELP, formatter_class=_Fmt)
    pi.add_argument("alias", help="Table alias")
    pi.add_argument("--json", action="store_true")

    return p


# ── Session loader ────────────────────────────────────────────────────────────

def _load_session(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Session:
    if not args.session:
        parser.print_help()
        print()
        print_error("--session PATH is required for this command.")
        print_error("Example:  bfx --session ./bfx_export list")
        print_error("Tip:      Run  bfx export --folder <path>  first to create the export.")
        sys.exit(1)
    try:
        return Session(args.session)
    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to load session: {e}")
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    # Apply colour flag before anything renders
    if args.no_color or os.environ.get("NO_COLOR") or os.environ.get("BFX_NO_COLOR"):
        Theme.disable()

    if not args.command:
        print_banner(__version__)
        parser.print_help()
        sys.exit(0)

    # export does NOT need --session
    if args.command == "export":
        cmd_export.run(
            folder    = args.folder,
            file      = args.file,
            output    = args.output,
            tables    = args.tables,
            limit     = args.limit,
            recursive = args.recursive,
        )
        return

    # All other commands need --session
    session = _load_session(args, parser)

    if args.command == "list":
        cmd_list.run(session, as_json=args.json)

    elif args.command == "view":
        cmd_view.run(session,
            alias=args.alias, rows=args.rows,
            as_json=args.json, export=args.export)

    elif args.command == "head":
        cmd_head_tail.run(session,
            alias=args.alias, rows=args.rows,
            from_end=False, as_json=args.json, export=args.export)

    elif args.command == "tail":
        cmd_head_tail.run(session,
            alias=args.alias, rows=args.rows,
            from_end=True, as_json=args.json, export=args.export)

    elif args.command == "search":
        cmd_search.run(session,
            keyword=args.keyword, table_filter=args.table,
            case_sensitive=args.case, col_filter=args.col,
            rows=args.rows, as_json=args.json, export=args.export)

    elif args.command == "filter":
        cols   = args.cols   or []
        values = args.values or []
        if len(cols) != len(values):
            print_error(
                f"{len(cols)} --col flag(s) but {len(values)} --value flag(s). "
                "Each --col must be paired with exactly one --value."
            )
            sys.exit(1)
        cmd_filter.run(session,
            alias=args.alias, conditions=list(zip(cols, values)),
            use_regex=args.regex, case_sensitive=args.case,
            rows=args.rows, as_json=args.json, export=args.export)

    elif args.command == "schema":
        cmd_schema.run(session,
            alias=args.alias, as_json=args.json, samples=args.samples)

    elif args.command == "summary":
        cmd_summary.run(session, as_json=args.json)

    elif args.command == "info":
        cmd_info.run(session, alias=args.alias, as_json=args.json)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
