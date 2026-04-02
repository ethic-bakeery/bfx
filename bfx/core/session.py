"""
bfx.core.session
────────────────
Loads a bfx export folder, discovers all CSV exports, builds a clean alias
registry (cluster_keywords.csv → cluster-keywords), reads forensic metadata
headers, and skips/reports empty tables.
"""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── Alias normalisation ───────────────────────────────────────────────────────

def _normalise_alias(name: str) -> str:
    """
    Convert any filename to a clean, CLI-friendly alias.
    cluster_duplicate_visits.csv  →  cluster-duplicate-visits
    Login Data For Account_logins →  login-data-for-account-logins
    """
    stem = Path(name).stem
    # Replace spaces, underscores, dots with hyphens; lowercase; strip extras
    alias = re.sub(r"[\s_\.]+", "-", stem).lower()
    alias = re.sub(r"-+", "-", alias).strip("-")
    return alias


# ── Per-table metadata ────────────────────────────────────────────────────────

@dataclass
class TableMeta:
    alias:        str            # CLI-friendly name (e.g. "urls")
    csv_path:     Path           # Absolute path to CSV file
    db_name:      str            # Source DB filename
    db_desc:      str            # Human description of DB
    table_name:   str            # Original SQL table name
    table_desc:   str            # Human description of table
    total_rows:   int            # Rows in source DB (from header)
    export_ts:    str            # When exported (UTC string)
    md5:          str            # MD5 of source DB
    headers:      List[str]      = field(default_factory=list)   # column names
    row_count:    int            = 0    # actual rows in this CSV
    is_empty:     bool           = False
    skipped:      bool           = False
    skip_reason:  str            = ""


# ── Forensic header parser ────────────────────────────────────────────────────

_META_KEYS = {
    "# Source DB":          "source_db",
    "# DB Description":     "db_desc",
    "# Table":              "table_name",
    "# Table Description":  "table_desc",
    "# Total Rows in DB":   "total_rows",
    "# Export Timestamp":   "export_ts",
    "# MD5 Hash of Source DB": "md5",
}

def _parse_csv_meta(path: Path) -> Tuple[dict, List[str], int]:
    """
    Read the forensic header block at the top of a bfx CSV.
    Returns (meta_dict, column_headers, data_row_count).
    """
    meta: dict = {}
    headers: List[str] = []
    data_rows = 0

    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f)
            in_meta = True
            for row in reader:
                if not row:
                    continue

                # Meta comment rows
                if in_meta and row[0].startswith("#"):
                    for key, attr in _META_KEYS.items():
                        if row[0].strip() == key and len(row) > 1:
                            meta[attr] = row[1].strip()
                    continue

                # First non-comment, non-blank row = column headers
                if in_meta:
                    in_meta = False
                    headers = [h.strip() for h in row]
                    continue

                data_rows += 1

    except Exception:
        pass

    return meta, headers, data_rows


# ── Session ───────────────────────────────────────────────────────────────────

class Session:
    """
    Represents one bfx export folder.

    Builds a complete alias → TableMeta registry on load.
    Reports skipped (empty, unreadable) tables clearly.
    """

    def __init__(self, export_dir: str | Path) -> None:
        self.export_dir = Path(export_dir).resolve()
        self._tables:   Dict[str, TableMeta] = {}   # alias → meta
        self._skipped:  List[TableMeta]      = []
        self._alias_map: Dict[str, str]      = {}   # alias → alias (for lookup)

        if not self.export_dir.exists():
            raise FileNotFoundError(
                f"Export folder not found: {self.export_dir}\n"
                "Run browser_forensic_exporter.py first, then point --session at its output."
            )
        self._load()

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Walk the export directory and register every CSV."""
        seen_aliases: Dict[str, int] = {}   # alias → collision counter

        csv_files = sorted(self.export_dir.rglob("*.csv"))
        # Exclude the manifest
        csv_files = [p for p in csv_files if p.name != "_FORENSIC_MANIFEST.csv"]

        for csv_path in csv_files:
            raw_alias = _normalise_alias(csv_path.stem)

            # Deduplicate aliases (e.g. two DBs both have a 'urls' table)
            if raw_alias in seen_aliases:
                seen_aliases[raw_alias] += 1
                # Prefix with parent folder name to disambiguate
                parent = _normalise_alias(csv_path.parent.name)
                alias = f"{parent}-{raw_alias}"
            else:
                seen_aliases[raw_alias] = 1
                alias = raw_alias

            meta_dict, headers, row_count = _parse_csv_meta(csv_path)

            # Determine skip / empty conditions
            skip     = False
            skip_why = ""

            if not headers:
                skip     = True
                skip_why = "no column headers found"
            elif row_count == 0:
                skip     = True
                skip_why = "table is empty (0 data rows)"

            # Infer DB name from parent folder
            db_folder = csv_path.parent.name

            tm = TableMeta(
                alias       = alias,
                csv_path    = csv_path,
                db_name     = meta_dict.get("source_db", db_folder),
                db_desc     = meta_dict.get("db_desc", db_folder),
                table_name  = meta_dict.get("table_name", csv_path.stem),
                table_desc  = meta_dict.get("table_desc", ""),
                total_rows  = _safe_int(meta_dict.get("total_rows", "0")),
                export_ts   = meta_dict.get("export_ts", ""),
                md5         = meta_dict.get("md5", ""),
                headers     = headers,
                row_count   = row_count,
                is_empty    = (row_count == 0),
                skipped     = skip,
                skip_reason = skip_why,
            )

            if skip:
                self._skipped.append(tm)
            else:
                self._tables[alias] = tm

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def tables(self) -> Dict[str, TableMeta]:
        return self._tables

    @property
    def skipped(self) -> List[TableMeta]:
        return self._skipped

    def get(self, alias: str) -> Optional[TableMeta]:
        """Resolve an alias (exact or prefix match)."""
        if alias in self._tables:
            return self._tables[alias]
        # Prefix / fuzzy match
        matches = [k for k in self._tables if k.startswith(alias)]
        if len(matches) == 1:
            return self._tables[matches[0]]
        if len(matches) > 1:
            raise KeyError(
                f"Ambiguous alias '{alias}' — matches: {', '.join(sorted(matches))}. "
                "Be more specific."
            )
        raise KeyError(
            f"Unknown table alias '{alias}'.\n"
            "Run  bfx --session <path> list  to see all available aliases."
        )

    def read_rows(
        self,
        alias: str,
        rows: Optional[int] = None,
        from_end: bool = False,
    ) -> Tuple[List[str], List[List[str]]]:
        """
        Read data rows from a table CSV.
        Returns (headers, rows_as_lists).
        Skips the forensic meta block automatically.
        Optionally limits to first/last N rows.
        """
        tm = self.get(alias)
        all_rows: List[List[str]] = []
        headers:  List[str]      = []
        in_meta = True

        with open(tm.csv_path, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                if in_meta and row[0].startswith("#"):
                    continue
                if in_meta:
                    in_meta  = False
                    headers  = [h.strip() for h in row]
                    continue
                all_rows.append([c.strip() for c in row])

        if rows is not None:
            all_rows = all_rows[-rows:] if from_end else all_rows[:rows]

        return headers, all_rows

    def read_all_for_search(
        self,
        keyword: str,
        case_sensitive: bool = False,
    ) -> List[Tuple[str, List[str], List[str]]]:
        """
        Search keyword across ALL tables.
        Returns list of (alias, headers, matching_rows).
        """
        import re as _re
        flags  = 0 if case_sensitive else _re.IGNORECASE
        pat    = _re.compile(_re.escape(keyword), flags)
        results = []

        for alias, tm in self._tables.items():
            headers, all_rows = self.read_rows(alias)
            matched = [r for r in all_rows if any(pat.search(str(c)) for c in r)]
            if matched:
                results.append((alias, headers, matched))

        return results

    def summary_stats(self) -> List[dict]:
        """Return summary statistics for every loaded table."""
        stats = []
        for alias, tm in sorted(self._tables.items()):
            stats.append({
                "alias":      alias,
                "table":      tm.table_name,
                "db":         Path(tm.db_name).name,
                "rows":       tm.row_count,
                "columns":    len(tm.headers),
                "source_rows": tm.total_rows,
                "exported":   tm.export_ts,
            })
        return stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
