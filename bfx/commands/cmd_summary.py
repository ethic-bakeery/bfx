"""
bfx summary
───────────
Session-wide statistics: row counts, date ranges, top domains, top searches.
The analyst's first stop for any new case.
"""

from __future__ import annotations
import json, re
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
bfx summary — Session-wide forensic overview
=============================================

Provides a high-level overview of the entire export:
  • Table inventory (row counts)
  • Top 10 visited domains
  • Top 10 search queries
  • Download statistics
  • Date range of activity

Usage:
  bfx --session <path> summary [OPTIONS]

Options:
  --json          Output as JSON

Examples:
  bfx --session ./exports summary
  bfx --session ./exports summary --json
"""


def run(session: Session, as_json: bool = False) -> None:

    stats: dict = {
        "tables":     [],
        "top_domains":[],
        "top_searches":[],
        "downloads":  {},
        "date_range": {},
    }

    # ── Table inventory ───────────────────────────────────────────────────────
    for alias in sorted(session.tables):
        tm = session.tables[alias]
        stats["tables"].append({
            "alias": alias,
            "rows":  tm.row_count,
            "db":    tm.db_desc,
        })

    # ── Top domains (from urls table) ─────────────────────────────────────────
    try:
        hdrs, data = session.read_rows("urls")
        domain_col = _find_col(hdrs, "__DOMAIN") or _find_col(hdrs, "url__DOMAIN")
        if domain_col is not None:
            domains = [row[domain_col].strip() for row in data
                       if domain_col < len(row) and row[domain_col].strip()
                       and row[domain_col].strip() not in ("", "None")]
            top = Counter(domains).most_common(10)
            stats["top_domains"] = [{"domain": d, "count": c} for d, c in top]
    except KeyError:
        pass

    # ── Top searches (keyword_search_terms) ───────────────────────────────────
    for alias in session.tables:
        if "keyword" in alias or "search" in alias:
            try:
                hdrs, data = session.read_rows(alias)
                term_col = _find_col(hdrs, "term") or _find_col(hdrs, "keyword")
                if term_col is not None:
                    terms = [row[term_col].strip() for row in data
                             if term_col < len(row) and row[term_col].strip()]
                    top = Counter(terms).most_common(10)
                    stats["top_searches"] = [{"term": t, "count": c} for t, c in top]
                break
            except Exception:
                pass

    # ── Downloads summary ─────────────────────────────────────────────────────
    for alias in session.tables:
        if "download" in alias:
            try:
                hdrs, data = session.read_rows(alias)
                stats["downloads"]["total_files"] = len(data)
                mime_col = _find_col(hdrs, "mime_type")
                if mime_col is not None:
                    mimes = [row[mime_col] for row in data
                             if mime_col < len(row) and row[mime_col].strip()]
                    top_mimes = Counter(mimes).most_common(5)
                    stats["downloads"]["top_mime_types"] = [
                        {"mime": m, "count": c} for m, c in top_mimes
                    ]
                break
            except Exception:
                pass

    # ── Date range (from visits) ──────────────────────────────────────────────
    for alias in session.tables:
        if alias in ("visits", "history-visits"):
            try:
                hdrs, data = session.read_rows(alias)
                human_col = _find_col(hdrs, "visit_time__HUMAN")
                if human_col is not None:
                    dates = sorted([
                        row[human_col].strip() for row in data
                        if human_col < len(row) and row[human_col].strip()
                        and row[human_col].strip() not in ("", "None")
                    ])
                    if dates:
                        stats["date_range"] = {
                            "earliest": dates[0],
                            "latest":   dates[-1],
                            "total_visits": len(data),
                        }
                break
            except Exception:
                pass

    # ── JSON output ───────────────────────────────────────────────────────────
    if as_json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    # ── Terminal output ───────────────────────────────────────────────────────
    print_section("Forensic Session Summary")

    # Table inventory
    print()
    print(style("  📂  Table Inventory", WHITE, BOLD))
    inv_rows = [[t["alias"], t["db"], f"{t['rows']:,}"] for t in stats["tables"]]
    TableRenderer(["Alias", "Source Database", "Rows"], inv_rows).print()

    if stats.get("date_range"):
        dr = stats["date_range"]
        print()
        print(style("  🕐  Activity Date Range", WHITE, BOLD))
        print_info(f"Earliest visit : {style(dr.get('earliest','?'), CYAN)}")
        print_info(f"Latest   visit : {style(dr.get('latest','?'), CYAN)}")
        print_info(f"Total  visits  : {style(str(dr.get('total_visits','?')), CYAN)}")

    if stats.get("top_domains"):
        print()
        print(style("  🌐  Top 10 Visited Domains", WHITE, BOLD))
        dom_rows = [[d["domain"], str(d["count"])] for d in stats["top_domains"]]
        TableRenderer(["Domain", "Count"], dom_rows).print()

    if stats.get("top_searches"):
        print()
        print(style("  🔍  Top 10 Search Queries", WHITE, BOLD))
        srch_rows = [[s["term"][:80], str(s["count"])] for s in stats["top_searches"]]
        TableRenderer(["Search Term", "Count"], srch_rows).print()

    if stats.get("downloads"):
        dl = stats["downloads"]
        print()
        print(style("  ⬇  Downloads", WHITE, BOLD))
        print_info(f"Total files : {style(str(dl.get('total_files', 0)), CYAN)}")
        if dl.get("top_mime_types"):
            mime_rows = [[m["mime"], str(m["count"])] for m in dl["top_mime_types"]]
            TableRenderer(["MIME Type", "Count"], mime_rows).print()

    if session.skipped:
        print()
        print(style(
            f"  ↷  {len(session.skipped)} table(s) skipped (empty/unreadable) "
            "— run  bfx list  for details.",
            DIM,
        ))


def _find_col(headers: list, keyword: str) -> Optional[int]:
    kw = keyword.lower()
    for i, h in enumerate(headers):
        if h.lower() == kw or h.lower().endswith(kw):
            return i
    return None
