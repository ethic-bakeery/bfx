#!/usr/bin/env python3
"""
Browser Forensic SQLite Exporter - Professional Edition
Supports Chrome, Edge, Firefox, Opera, Brave, Safari
Exports all browser artifacts with human-readable timestamps and forensic metadata
"""

import sqlite3
import os
import sys
import csv
import tempfile
import shutil
import logging
import json
import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import argparse
import traceback

# ── Logging Setup ────────────────────────────────────────────────────────────
def setup_logging(output_dir):
    log_path = Path(output_dir) / "forensic_export.log"
    handlers = [
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=handlers
    )
    return logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# ── Timestamp Conversion ─────────────────────────────────────────────────────
WEBKIT_EPOCH   = datetime(1601, 1, 1, tzinfo=timezone.utc)
UNIX_EPOCH     = datetime(1970, 1, 1, tzinfo=timezone.utc)
COCOA_EPOCH    = datetime(2001, 1, 1, tzinfo=timezone.utc)

def convert_timestamp(value):
    """
    Auto-detect and convert any browser timestamp to ISO-8601 UTC string.
    Returns (iso_string, format_name) or (None, 'unknown').
    """
    if value is None or value == '' or value == 0:
        return None, 'null'
    try:
        ts = float(value)
        if ts <= 0:
            return None, 'null'

        # WebKit / Chrome: microseconds since 1601-01-01
        if 11_000_000_000_000_000 < ts < 17_000_000_000_000_000:
            dt = WEBKIT_EPOCH + timedelta(microseconds=ts)
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC'), 'WebKit (Chrome)'

        # Unix milliseconds
        if 1_000_000_000_000 < ts < 9_999_999_999_999:
            dt = UNIX_EPOCH + timedelta(milliseconds=ts)
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC'), 'Unix ms'

        # Unix seconds
        if 1_000_000_000 < ts < 9_999_999_999:
            dt = UNIX_EPOCH + timedelta(seconds=ts)
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC'), 'Unix s'

        # Apple Cocoa: seconds since 2001-01-01
        if 100_000_000 < ts < 2_000_000_000 and ts < 1_000_000_000:
            dt = COCOA_EPOCH + timedelta(seconds=ts)
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC'), 'Apple Cocoa'

        return None, 'unknown'
    except (ValueError, TypeError, OverflowError, OSError):
        return None, 'error'

# ── Column Intelligence ──────────────────────────────────────────────────────
TIMESTAMP_KEYWORDS = [
    'time', 'date', 'stamp', 'created', 'modified', 'accessed',
    'last', 'epoch', 'visit', 'expir', 'birth', 'install',
    'first', 'session', 'start', 'end', 'download', 'added'
]

URL_KEYWORDS = ['url', 'origin', 'host', 'domain', 'referrer', 'source', 'target', 'redirect']

def is_timestamp_column(col_name):
    col = col_name.lower()
    return any(kw in col for kw in TIMESTAMP_KEYWORDS)

def is_url_column(col_name):
    col = col_name.lower()
    return any(kw in col for kw in URL_KEYWORDS)

def extract_domain(url_value):
    """Extract domain from URL safely."""
    if not url_value or not isinstance(url_value, str):
        return None
    try:
        parsed = urlparse(url_value if '://' in url_value else 'http://' + url_value)
        return parsed.netloc or None
    except Exception:
        return None

def categorize_url(url_value):
    """Categorize URL by type."""
    if not url_value or not isinstance(url_value, str):
        return None
    url_lower = url_value.lower()
    if url_lower.startswith('chrome://') or url_lower.startswith('edge://'):
        return 'Browser Internal'
    elif url_lower.startswith('chrome-extension://') or url_lower.startswith('moz-extension://'):
        return 'Extension'
    elif url_lower.startswith('file://'):
        return 'Local File'
    elif url_lower.startswith('data:'):
        return 'Data URI'
    elif url_lower.startswith('http://'):
        return 'HTTP'
    elif url_lower.startswith('https://'):
        return 'HTTPS'
    elif url_lower.startswith('ftp://'):
        return 'FTP'
    else:
        return 'Other'

# ── Database Schema Intelligence ─────────────────────────────────────────────
# Maps known Chrome/Edge database files to human-readable names
KNOWN_DB_FILES = {
    'history':               'Browsing History & Downloads',
    'web data':              'Autofill, Forms & Credit Cards',
    'login data':            'Saved Passwords (Hashed)',
    'login data for account':'Signed-In Account Passwords (Hashed)',
    'favicons':              'Website Favicons',
    'top sites':             'Most Visited Sites',
    'network action predictor': 'Omnibox Predictions',
    'affiliation database':  'Credential Affiliations',
    'conversions':           'Ad Conversion Tracking',
    'dips':                  'DIPS Privacy Bounce Tracker',
    'extension cookies':     'Extension Cookies',
    'shortcuts':             'Omnibox Shortcut History',
    'quota manager':         'Storage Quota Info',
}

KNOWN_TABLES = {
    # History DB
    'urls':             'All visited URLs with visit counts and titles',
    'visits':           'Individual page visit events with timestamps',
    'downloads':        'Download history (files, sources, times)',
    'downloads_url_chains': 'Download redirect chain URLs',
    'keyword_search_terms': 'Search queries typed by user',
    'segments':         'URL path segments for omnibox',
    'visit_source':     'Source of each visit (typed, link, etc.)',
    # Web Data DB
    'autofill':         'Autofill form field values',
    'autofill_profiles':'Saved name/address profiles',
    'credit_cards':     'Saved credit card info (encrypted)',
    'keywords':         'Omnibox search engines',
    'ie7_logins':       'Migrated IE7 login data',
    'masked_credit_cards': 'Google Pay card tokens',
    # Login Data DB
    'logins':           'Saved login credentials (passwords encrypted)',
    # Favicons DB
    'favicons':         'Favicon image data (binary)',
    'favicon_bitmaps':  'Favicon bitmap data',
    'icon_mapping':     'URL to favicon mapping',
    # Cookies (if present)
    'cookies':          'Browser cookies (names, values, expiry)',
    # Top Sites
    'top_sites':        'Top visited sites list',
    'thumbnails':       'Site thumbnail data',
}

# ── Safe DB Connection ───────────────────────────────────────────────────────
def open_db(db_path):
    """Open SQLite DB read-only, falling back to temp-copy for locked files."""
    temp_dir = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
        conn.row_factory = sqlite3.Row
        conn.text_factory = lambda b: b.decode('utf-8', errors='replace') if isinstance(b, bytes) else b
        conn.execute("SELECT 1")  # Test connection
        return conn, None
    except Exception:
        pass

    try:
        temp_dir = tempfile.mkdtemp(prefix='bforensic_')
        temp_path = os.path.join(temp_dir, Path(db_path).name)
        shutil.copy2(db_path, temp_path)
        # Also copy WAL/SHM if present
        for suffix in ['-wal', '-shm']:
            extra = str(db_path) + suffix
            if os.path.exists(extra):
                shutil.copy2(extra, temp_path + suffix)
        conn = sqlite3.connect(temp_path)
        conn.row_factory = sqlite3.Row
        conn.text_factory = lambda b: b.decode('utf-8', errors='replace') if isinstance(b, bytes) else b
        return conn, temp_dir
    except Exception as e:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Cannot open database: {e}")

def is_sqlite(path):
    """Check SQLite magic bytes."""
    try:
        if os.path.getsize(path) < 100:
            return False
        with open(path, 'rb') as f:
            return f.read(16).startswith(b'SQLite format 3\x00')
    except Exception:
        return False

def get_db_file_hash(path):
    """MD5 hash for forensic integrity."""
    h = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return 'N/A'

# ── Row Value Sanitizer ──────────────────────────────────────────────────────
def sanitize_value(value):
    """Make any SQLite value safe and readable for CSV."""
    if value is None:
        return ''
    if isinstance(value, bytes):
        # Show hex for binary blobs, truncated
        if len(value) > 64:
            return f'<BLOB {len(value)} bytes: {value[:32].hex()}...>'
        return f'<BLOB: {value.hex()}>'
    if isinstance(value, str):
        # Remove null bytes and control chars
        value = value.replace('\x00', '').replace('\r', ' ')
        return value.strip()
    return value

# ── Main Exporter Class ──────────────────────────────────────────────────────
class BrowserForensicExporter:
    def __init__(self, output_dir='./export'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        global logger
        logger = setup_logging(output_dir)

        self.stats = {
            'databases': 0,
            'tables': 0,
            'rows': 0,
            'errors': 0,
            'skipped': 0,
        }
        self.manifest = []  # Forensic manifest of all exported files

    # ── Table Export ─────────────────────────────────────────────────────────
    def export_table(self, conn, db_path, table_name, output_path, row_limit=None):
        """Export one table to CSV with enriched forensic columns."""
        # ── CRITICAL FIX: use THREE independent cursors so that schema lookup,
        # row-count query, and data fetch never overwrite each other's state.
        # Previously a single shared cursor was reused for all three operations,
        # causing every table to export the same (last) result set.
        schema_cur = conn.cursor()
        meta_cur   = conn.cursor()
        data_cur   = conn.cursor()

        # Get schema
        try:
            schema_cur.execute(f"PRAGMA table_info([{table_name}])")
            schema = schema_cur.fetchall()
        except Exception as e:
            logger.error(f"  Schema error for {table_name}: {e}")
            return 0
        finally:
            schema_cur.close()

        if not schema:
            logger.warning(f"  Empty schema for {table_name}, skipping.")
            return 0

        col_names = [row['name'] for row in schema]

        # Identify special columns
        ts_cols  = [c for c in col_names if is_timestamp_column(c)]
        url_cols = [c for c in col_names if is_url_column(c)]

        # Build output header: original cols + enrichment cols
        extra_headers = []
        for c in ts_cols:
            extra_headers += [f'{c}__HUMAN', f'{c}__FORMAT']
        for c in url_cols:
            extra_headers += [f'{c}__DOMAIN', f'{c}__CATEGORY']

        all_headers = col_names + extra_headers

        # Forensic metadata
        db_label    = KNOWN_DB_FILES.get(Path(db_path).stem.lower(), Path(db_path).name)
        table_label = KNOWN_TABLES.get(table_name.lower(), table_name)

        # Count rows — uses its own cursor so it never touches the data cursor
        try:
            meta_cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            total_rows = meta_cur.fetchone()[0]
        except Exception:
            total_rows = '?'
        finally:
            meta_cur.close()

        # Fetch data — dedicated cursor, opened last so nothing else can stomp on it
        query = f"SELECT * FROM [{table_name}]"
        if row_limit:
            query += f" LIMIT {row_limit}"

        try:
            data_cur.execute(query)
        except Exception as e:
            logger.error(f"  Query error for {table_name}: {e}")
            data_cur.close()
            return 0

        rows_written = 0
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:  # utf-8-sig for Excel BOM
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)

            # Forensic header block
            writer.writerow(['# BROWSER FORENSIC EXPORT'])
            writer.writerow(['# Source DB', str(db_path)])
            writer.writerow(['# DB Description', db_label])
            writer.writerow(['# Table', table_name])
            writer.writerow(['# Table Description', table_label])
            writer.writerow(['# Total Rows in DB', total_rows])
            writer.writerow(['# Export Timestamp', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')])
            writer.writerow(['# MD5 Hash of Source DB', get_db_file_hash(db_path)])
            if row_limit:
                writer.writerow(['# NOTE', f'Row limit applied: {row_limit}'])
            writer.writerow([])  # Blank separator

            # Column header
            writer.writerow(all_headers)

            # Data rows — stream in chunks using the dedicated data cursor
            chunk = 500
            while True:
                batch = data_cur.fetchmany(chunk)
                if not batch:
                    break
                for row in batch:
                    base_values = [sanitize_value(row[c]) for c in col_names]
                    extras = []

                    for c in ts_cols:
                        raw = row[c] if c in col_names else None
                        human, fmt = convert_timestamp(raw)
                        extras += [human or '', fmt]

                    for c in url_cols:
                        raw = row[c] if c in col_names else None
                        extras += [
                            extract_domain(str(raw)) or '',
                            categorize_url(str(raw)) or ''
                        ]

                    writer.writerow(base_values + extras)
                    rows_written += 1

        data_cur.close()
        return rows_written

    # ── Database Export ───────────────────────────────────────────────────────
    def export_database(self, db_path, tables_filter=None, row_limit=None):
        db_path = Path(db_path)
        if not is_sqlite(db_path):
            logger.warning(f"Not a SQLite file, skipping: {db_path.name}")
            self.stats['skipped'] += 1
            return

        db_label = KNOWN_DB_FILES.get(db_path.stem.lower(), db_path.stem)
        logger.info(f"\n{'='*60}")
        logger.info(f"  DATABASE: {db_path.name}  [{db_label}]")
        logger.info(f"  Size: {db_path.stat().st_size:,} bytes")
        logger.info(f"{'='*60}")

        conn = None
        temp_dir = None
        try:
            conn, temp_dir = open_db(db_path)

            # Get tables
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            all_tables = [row[0] for row in cursor.fetchall()]

            if tables_filter:
                tables = [t for t in all_tables if t.lower() in [x.lower() for x in tables_filter]]
            else:
                tables = all_tables

            if not tables:
                logger.info(f"  No tables found.")
                return

            logger.info(f"  Tables found: {', '.join(tables)}")

            # Safe directory name for this DB
            safe_db = re.sub(r'[^\w\-]', '_', db_path.stem)
            db_out_dir = self.output_dir / safe_db
            db_out_dir.mkdir(exist_ok=True)

            for table in tables:
                table_label = KNOWN_TABLES.get(table.lower(), table)
                safe_table = re.sub(r'[^\w\-]', '_', table)
                csv_path = db_out_dir / f"{safe_table}.csv"

                logger.info(f"  → Exporting [{table}] ({table_label})")
                rows = self.export_table(conn, db_path, table, csv_path, row_limit)
                logger.info(f"    ✓ {rows:,} rows → {csv_path.name}")

                self.stats['rows'] += rows
                self.stats['tables'] += 1
                self.manifest.append({
                    'source_db': str(db_path),
                    'table': table,
                    'description': table_label,
                    'rows_exported': rows,
                    'csv_file': str(csv_path),
                })

            self.stats['databases'] += 1

        except Exception as e:
            logger.error(f"  FAILED: {db_path.name}: {e}")
            logger.debug(traceback.format_exc())
            self.stats['errors'] += 1
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ── Folder Scan ──────────────────────────────────────────────────────────
    def export_folder(self, folder_path, recursive=False, tables_filter=None, row_limit=None):
        folder = Path(folder_path)
        if not folder.exists():
            logger.error(f"Folder does not exist: {folder}")
            return

        extensions = {'.sqlite', '.db', '.sqlite3', '.db3', '.s3db', '.sl3'}
        pattern = '**/*' if recursive else '*'
        candidates = []

        for p in folder.glob(pattern):
            if p.is_file():
                if p.suffix.lower() in extensions or is_sqlite(p):
                    candidates.append(p)

        logger.info(f"\nFound {len(candidates)} SQLite file(s) in: {folder}")
        for db in candidates:
            self.export_database(db, tables_filter, row_limit)

    # ── Manifest & Summary ───────────────────────────────────────────────────
    def write_manifest(self):
        manifest_path = self.output_dir / '_FORENSIC_MANIFEST.csv'
        with open(manifest_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['source_db', 'table', 'description', 'rows_exported', 'csv_file'])
            writer.writeheader()
            writer.writerows(self.manifest)
        logger.info(f"\nManifest written: {manifest_path}")
        return manifest_path

    def print_summary(self):
        lines = [
            '',
            '╔' + '═'*54 + '╗',
            '║    BROWSER FORENSIC EXPORT — COMPLETE SUMMARY          ║',
            '╠' + '═'*54 + '╣',
            f'║  Databases processed : {self.stats["databases"]:<31}║',
            f'║  Tables exported     : {self.stats["tables"]:<31}║',
            f'║  Total rows exported : {self.stats["rows"]:<31,}║',
            f'║  Files skipped       : {self.stats["skipped"]:<31}║',
            f'║  Errors              : {self.stats["errors"]:<31}║',
            f'║  Output directory    : {str(self.output_dir)[:31]:<31}║',
            '╚' + '═'*54 + '╝',
        ]
        for line in lines:
            print(line)

# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='Browser Forensic SQLite Exporter — Professional Edition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export everything in a folder (like Chrome's User Data/Default/)
  python browser_forensic_exporter.py --folder "C:/Users/User/AppData/Local/Google/Chrome/User Data/Default"

  # Export a single DB
  python browser_forensic_exporter.py --file History --output ./exports

  # Export specific tables only
  python browser_forensic_exporter.py --file History --tables urls,visits

  # Preview mode (first 500 rows)
  python browser_forensic_exporter.py --folder ./Browser --limit 500

  # Recursive scan with custom output
  python browser_forensic_exporter.py --folder ./forensic_image --recursive --output ./case_exports
        """
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file',   help='Single SQLite database file')
    group.add_argument('--folder', help='Folder of browser databases')

    parser.add_argument('--recursive', action='store_true', help='Scan subfolders')
    parser.add_argument('--output',  default='./browser_forensic_export', help='Output directory')
    parser.add_argument('--tables',  help='Comma-separated table filter (e.g. urls,visits,logins)')
    parser.add_argument('--limit',   type=int, help='Max rows per table (for preview)')

    args = parser.parse_args()
    tables_filter = [t.strip() for t in args.tables.split(',')] if args.tables else None

    exporter = BrowserForensicExporter(output_dir=args.output)
    logger.info('Browser Forensic Exporter — Starting')
    logger.info(f'Output directory: {args.output}')

    try:
        if args.file:
            exporter.export_database(args.file, tables_filter, args.limit)
        else:
            exporter.export_folder(args.folder, args.recursive, tables_filter, args.limit)

        exporter.write_manifest()
        exporter.print_summary()

    except KeyboardInterrupt:
        logger.info('\nExport interrupted by user.')
    except Exception as e:
        logger.error(f'Fatal error: {e}')
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
