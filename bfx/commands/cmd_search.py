"""
bfx search
──────────
Search a keyword across ALL tables simultaneously.
Shows which table each hit came from, highlights the matching term.
Supports export of all hits to a single CSV or JSON file.
"""

from __future__ import annotations
import csv, json, re, sys
from pathlib import Path
from typing import Optional
from bfx.core  import Session, export_csv, rows_to_json_str
from bfx.ui.terminal import (
    Theme, style, terminal_width,
    print_section, print_info, print_ok, print_warn, print_error, print_skip,
    TableRenderer, Paginator,
    BOLD, DIM, RED, GREEN, YELLOW, BLUE, CYAN, WHITE, BG_NAVY,
)


HELP = """
bfx search — Search a keyword across all tables
================================================

Searches every loaded table for rows containing the keyword.
Results are grouped by table, showing alias and description above each hit set.

Usage:
  bfx --session <path> search <keyword> [OPTIONS]

Arguments:
  keyword         Text to search for (case-insensitive by default)

Options:
  --table ALIAS   Limit search to one specific table alias
  --case          Enable case-sensitive matching
  --col COLUMN    Search only within a specific column name
  --rows N        Max matching rows to show per table (default: 50)
  --json          Output all hits as JSON
  --export FILE   Export all hits to FILE (.csv or .json)

Examples:
  bfx --session ./exports search "lazarus"
  bfx --session ./exports search "gmail.com" --table urls
  bfx --session ./exports search "download" --col url --rows 20
  bfx --session ./exports search "192.168" --export ./ip_hits.csv
  bfx --session ./exports search "password" --json | jq '.[].rows | length'
"""


def _highlight(text: str, pattern: re.Pattern) -> str:
    """Highlight all matches of pattern in text with yellow bold."""
    def _repl(m: re.Match) -> str:
        return style(m.group(0), YELLOW, BOLD)
    return pattern.sub(_repl, str(text))


def run(
    session:        Session,
    keyword:        str,
    table_filter:   Optional[str] = None,
    case_sensitive: bool = False,
    col_filter:     Optional[str] = None,
    rows:           int = 50,
    as_json:        bool = False,
    export:         Optional[str] = None,
) -> None:

    if not keyword.strip():
        print_error("Search keyword cannot be empty.")
        return

    flags   = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(keyword), flags)

    # Determine which tables to search
    if table_filter:
        try:
            tm = session.get(table_filter)
            search_aliases = [table_filter]
        except KeyError as e:
            print_error(str(e))
            return
    else:
        search_aliases = sorted(session.tables.keys())

    # ── Collect hits ──────────────────────────────────────────────────────────
    all_results = []   # list of (alias, tm, headers, matched_rows)
    total_hits  = 0

    for alias in search_aliases:
        try:
            hdrs, data = session.read_rows(alias)
        except Exception as e:
            print_warn(f"Could not read '{alias}': {e}")
            continue

        tm = session.tables[alias]

        # Column filter
        if col_filter:
            col_lower = [h.lower() for h in hdrs]
            if col_filter.lower() not in col_lower:
                continue
            col_idx = col_lower.index(col_filter.lower())
            matched = [r for r in data if pattern.search(str(r[col_idx]) if col_idx < len(r) else "")]
        else:
            matched = [r for r in data if any(pattern.search(str(c)) for c in r)]

        if matched:
            all_results.append((alias, tm, hdrs, matched[:rows]))
            total_hits += len(matched)

    # ── No results ────────────────────────────────────────────────────────────
    if not all_results:
        print_warn(f"No matches found for  '{keyword}'")
        scope = f"in table '{table_filter}'" if table_filter else "across all tables"
        print_info(f"Searched {scope}  ({len(search_aliases)} table(s))")
        return

    # ── JSON output ───────────────────────────────────────────────────────────
    if as_json:
        out = []
        for alias, tm, hdrs, matched in all_results:
            out.append({
                "alias":       alias,
                "table":       tm.table_name,
                "description": tm.table_desc,
                "hit_count":   len(matched),
                "rows":        [dict(zip(hdrs, r)) for r in matched],
            })
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # ── Export ────────────────────────────────────────────────────────────────
    if export:
        _export_all_hits(export, keyword, all_results)

    # ── Terminal output ───────────────────────────────────────────────────────
    print_section(
        f"Search results for  \"{keyword}\"  "
        f"— {total_hits} hit(s) across {len(all_results)} table(s)"
    )

    all_lines: list[str] = []

    for alias, tm, hdrs, matched in all_results:
        # Section header for this table
        all_lines.append("")
        all_lines.append(
            style(f"  ┌─ {alias}", GREEN, BOLD)
            + style(f"  [{tm.table_desc or tm.table_name}]  "
                    f"{len(matched)} hit(s)", DIM)
        )

        # Highlight matches in each cell
        highlighted = []
        for row in matched:
            highlighted.append([_highlight(c, pattern) for c in row])

        renderer = TableRenderer(hdrs, highlighted)
        all_lines.extend(renderer.render())

    if not export:
        all_lines.append("")
        all_lines.append(
            style(
                f"  Tip: add  --export hits.csv  to save all {total_hits} hits.",
                DIM,
            )
        )

    Paginator(all_lines).display()


def _export_all_hits(
    path: str,
    keyword: str,
    results: list,
) -> None:
    """Export all hits from all tables into one CSV/JSON, with a 'source_alias' column."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        if path.endswith(".json"):
            out = []
            for alias, tm, hdrs, matched in results:
                for row in matched:
                    rec = {"bfx_source_alias": alias}
                    rec.update(dict(zip(hdrs, row)))
                    out.append(rec)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
        else:
            # Determine superset of headers across all tables
            all_headers_set: list[str] = ["bfx_source_alias"]
            seen: set[str] = set()
            for _, _, hdrs, _ in results:
                for h in hdrs:
                    if h not in seen:
                        all_headers_set.append(h)
                        seen.add(h)

            with open(dest, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow([f"# bfx search export — keyword: {keyword}"])
                w.writerow([])
                w.writerow(all_headers_set)
                for alias, _, hdrs, matched in results:
                    for row in matched:
                        rec = dict(zip(hdrs, row))
                        out_row = [alias] + [rec.get(h, "") for h in all_headers_set[1:]]
                        w.writerow(out_row)

        total = sum(len(m) for _, _, _, m in results)
        print_ok(f"Exported {total:,} hits → {dest}")
    except Exception as e:
        print_error(f"Export failed: {e}")
