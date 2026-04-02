"""
bfx.ui.terminal
───────────────
All terminal rendering. Plain-text first — no box-drawing characters,
no ANSI codes unless the terminal explicitly supports them.
Cross-platform: Windows CMD, PowerShell, Windows Terminal, Unix.
"""

from __future__ import annotations

import os
import sys
import shutil
import re as _re
from typing import List, Optional

# ── Colour support detection ──────────────────────────────────────────────────

def _supports_color() -> bool:
    """Only enable colour when we are certain the terminal will render it."""
    if os.environ.get("BFX_NO_COLOR") or os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        # Only trust colour in Windows Terminal or VS Code terminal
        return bool(
            os.environ.get("WT_SESSION")      # Windows Terminal
            or os.environ.get("TERM_PROGRAM") # VS Code
            or os.environ.get("COLORTERM")    # Any 24-bit colour terminal
        )
    return True   # Unix/Mac: safe by default


class Theme:
    enabled: bool = _supports_color()

    @classmethod
    def disable(cls) -> None:
        cls.enabled = False

    @classmethod
    def enable(cls) -> None:
        cls.enabled = True


def _c(*codes: str) -> str:
    return "".join(codes) if Theme.enabled else ""

def _r() -> str:
    return "\033[0m" if Theme.enabled else ""

def style(text: str, *codes: str) -> str:
    if not Theme.enabled:
        return text
    return f"{''.join(codes)}{text}\033[0m"

# Common codes (only applied when Theme.enabled)
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"
BG_NAVY = "\033[48;5;17m"


# ── Terminal size ─────────────────────────────────────────────────────────────

def terminal_width() -> int:
    return shutil.get_terminal_size((100, 40)).columns

def terminal_height() -> int:
    return shutil.get_terminal_size((100, 40)).lines


# ── Visible length (strip ANSI for width math) ────────────────────────────────

_ANSI = _re.compile(r"\033\[[0-9;]*m")

def vlen(s: str) -> int:
    return len(_ANSI.sub("", s))

def rpad(s: str, width: int, char: str = " ") -> str:
    return s + char * max(width - vlen(s), 0)


# ── Print helpers ─────────────────────────────────────────────────────────────

def print_banner(version: str = "1.0.0") -> None:
    print()
    print(style(f"  BFX  Browser Forensic Explorer  v{version}", BOLD, WHITE))
    print(style(f"  Pure Python 3.8+  |  Zero dependencies", DIM))
    print()

def print_section(title: str) -> None:
    w = min(terminal_width(), 80)
    print()
    print(style(f"  {title}", BOLD, WHITE))
    print(style("  " + "-" * (w - 2), DIM))

def print_info(msg: str)  -> None: print(f"  [i]  {msg}")
def print_ok(msg: str)    -> None: print(f"  [ok] {msg}")
def print_warn(msg: str)  -> None: print(f"  [!]  {msg}", file=sys.stderr)
def print_error(msg: str) -> None: print(f"  [x]  {msg}", file=sys.stderr)
def print_skip(msg: str)  -> None: print(f"  [-]  {msg}")
def print_rule()          -> None: print(style("  " + "-" * 60, DIM))


# ── Plain-text table renderer ─────────────────────────────────────────────────
# No box-drawing. Uses column padding and a header separator line.

MAX_COL_W = 45
MIN_COL_W = 6
CARD_THRESHOLD = 7   # more columns than this → card view


def _col_widths(headers: List[str], rows: List[List[str]]) -> List[int]:
    n      = len(headers)
    widths = [min(max(vlen(h), MIN_COL_W), MAX_COL_W) for h in headers]
    for row in rows:
        for i in range(n):
            val = str(row[i]) if i < len(row) else ""
            widths[i] = min(max(widths[i], vlen(val[:MAX_COL_W])), MAX_COL_W)
    # Scale down proportionally if wider than terminal
    usable = terminal_width() - (n * 2) - 4
    total  = sum(widths)
    if total > usable and usable > 0:
        widths = [max(int(w * usable / total), MIN_COL_W) for w in widths]
    return widths


def _cell(val: str, width: int, col: str = "", bold: bool = False) -> str:
    val = str(val) if val is not None else ""
    if vlen(val) > width:
        val = val[: width - 1] + "~"
    padded = rpad(val, width)
    if bold:
        return style(padded, BOLD, WHITE)
    return _colour_value(col, padded)


def _colour_value(col: str, val: str) -> str:
    if not Theme.enabled:
        return val
    c = col.lower()
    if "url" in c or "referrer" in c:
        if "https://" in val:
            return style(val, GREEN)
        if "http://" in val:
            return style(val, YELLOW)
    if "path" in c or "target" in c:
        return style(val, CYAN)
    if c == "danger_type" and val.strip() not in ("0", ""):
        return style(val, RED, BOLD)
    return val


def render_table(
    headers: List[str],
    rows:    List[List[str]],
    title:   str = "",
    indent:  int = 2,
    highlight_pat=None,
) -> List[str]:
    """Render a plain-text aligned table with no box-drawing characters."""
    lines: List[str] = []
    pad   = " " * indent
    cw    = _col_widths(headers, rows)

    if title:
        lines.append(pad + style(title, BOLD, WHITE))

    # Header row
    hdr_cells = [_cell(h, cw[i], bold=True) for i, h in enumerate(headers)]
    lines.append(pad + "  ".join(hdr_cells))

    # Separator
    sep_parts = ["-" * cw[i] for i in range(len(headers))]
    lines.append(pad + style("  ".join(sep_parts), DIM))

    # Data rows
    for row in rows:
        cells = []
        for i, h in enumerate(headers):
            raw = str(row[i]) if i < len(row) else ""
            if highlight_pat:
                raw = highlight_pat.sub(
                    lambda m: style(m.group(0), YELLOW, BOLD), raw
                )
            cells.append(_cell(raw, cw[i], col=h))
        lines.append(pad + "  ".join(cells))

    lines.append(pad + style(f"{len(rows)} row(s)", DIM))
    return lines


def render_cards(
    headers:       List[str],
    rows:          List[List[str]],
    title:         str = "",
    highlight_pat=None,
) -> List[str]:
    """
    Vertical card layout — one record per block.
    Enrichment columns (__HUMAN, __FORMAT, __DOMAIN, __CATEGORY) are shown
    inline under their parent column, not as separate rows.
    Empty fields are hidden.
    """
    lines: List[str] = []
    tw    = min(terminal_width(), 90)
    pad   = "  "

    if title:
        lines.append(style(f"  {title}", BOLD, WHITE))

    # Separate original vs enrichment columns
    orig_hdrs   = [h for h in headers if not h.endswith(("__HUMAN","__FORMAT","__DOMAIN","__CATEGORY"))]
    enrich_sfxs = ("__HUMAN","__FORMAT","__DOMAIN","__CATEGORY")

    label_w = min(max((len(h) for h in orig_hdrs), default=12), 26)

    def get_enrich(row: List[str], base: str) -> dict:
        out = {}
        for sfx in enrich_sfxs:
            col = base + sfx
            if col in headers:
                idx = headers.index(col)
                v   = row[idx].strip() if idx < len(row) else ""
                if v and v not in ("None", "unknown", "null", ""):
                    out[sfx.lstrip("_")] = v
        return out

    for r_idx, row in enumerate(rows):
        lines.append(pad + style(f"Record {r_idx + 1}", BOLD, CYAN))
        lines.append(pad + style("-" * (tw - 4), DIM))

        for h in orig_hdrs:
            if h not in headers:
                continue
            idx = headers.index(h)
            raw = row[idx].strip() if idx < len(row) else ""

            if not raw or raw in ("None", ""):
                continue

            label     = rpad(h, label_w)
            val_disp  = _colour_value(h, raw)
            if highlight_pat:
                val_disp = highlight_pat.sub(
                    lambda m: style(m.group(0), YELLOW, BOLD), val_disp
                )
            # Truncate very long values
            max_v = tw - label_w - 8
            if vlen(raw) > max_v:
                val_disp = val_disp[: max_v + 20] + "~"  # rough — ANSI chars don't count

            lines.append(f"{pad}  {style(label, CYAN)}  {val_disp}")

            # Inline enrichment
            em = get_enrich(row, h)
            if em:
                parts = []
                if em.get("HUMAN"):
                    parts.append(style(em["HUMAN"], GREEN))
                if em.get("FORMAT"):
                    parts.append(style(f'({em["FORMAT"]})', DIM))
                if em.get("DOMAIN"):
                    parts.append(style(em["DOMAIN"], CYAN))
                if em.get("CATEGORY"):
                    cat_map = {"HTTPS": GREEN, "HTTP": YELLOW,
                               "Extension": "\033[95m", "Local File": CYAN}
                    parts.append(style(em["CATEGORY"], cat_map.get(em["CATEGORY"], WHITE)))
                prefix = " " * (label_w + 6)
                lines.append(f"{pad}  {prefix}-> {' | '.join(parts)}")

        lines.append("")

    lines.append(style(f"  {len(rows)} record(s)", DIM))
    return lines


# ── Unified renderer ──────────────────────────────────────────────────────────

class TableRenderer:
    def __init__(
        self,
        headers:       List[str],
        rows:          List[List[str]],
        title:         str = "",
        force_cards:   bool = False,
        force_table:   bool = False,
        highlight_pat  = None,
    ):
        self.headers       = headers
        self.rows          = rows
        self.title         = title
        self.highlight_pat = highlight_pat
        self._cards        = force_cards or (not force_table and len(headers) > CARD_THRESHOLD)

    def render(self) -> List[str]:
        if self._cards:
            return render_cards(self.headers, self.rows,
                                title=self.title, highlight_pat=self.highlight_pat)
        return render_table(self.headers, self.rows,
                            title=self.title, highlight_pat=self.highlight_pat)

    def print(self) -> None:
        for line in self.render():
            print(line)


# ── Cross-platform paginator ──────────────────────────────────────────────────

class Paginator:
    HELP = "  [SPACE]=next  [B]=prev  [G]=top  [Q]=quit"

    def __init__(self, lines: List[str], page_size: Optional[int] = None) -> None:
        self.lines     = lines
        self.page_size = page_size or max(terminal_height() - 4, 10)
        self.pos       = 0

    def _getch(self) -> str:
        try:
            if sys.platform == "win32":
                import msvcrt
                ch = msvcrt.getwch()
                if ch in ('\x00', '\xe0'):
                    msvcrt.getwch()
                    return ''
                return ch.lower()
            else:
                import tty, termios
                fd  = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    return sys.stdin.read(1).lower()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            return 'q'

    def _status(self, cur: int, tot: int) -> str:
        end  = min(self.pos + self.page_size, len(self.lines))
        pct  = min(int(100 * end / max(len(self.lines), 1)), 100)
        info = f"  Page {cur}/{tot}  Lines {self.pos+1}-{end}/{len(self.lines)} ({pct}%)  {self.HELP}"
        return info

    def display(self) -> None:
        # Not interactive or fits on one page: just print
        if not sys.stdout.isatty() or len(self.lines) <= self.page_size:
            for line in self.lines:
                print(line)
            return

        total_pages = max(1, -(-len(self.lines) // self.page_size))

        while True:
            print("\033[2J\033[H", end="", flush=True)
            cur = self.pos // self.page_size + 1
            chunk = self.lines[self.pos: self.pos + self.page_size]
            for line in chunk:
                print(line)
            for _ in range(self.page_size - len(chunk)):
                print()
            print(self._status(cur, total_pages), end="", flush=True)

            key = self._getch()
            if key in (" ", "f", "\r", "\n", ""):
                if self.pos + self.page_size < len(self.lines):
                    self.pos += self.page_size
            elif key == "b":
                self.pos = max(0, self.pos - self.page_size)
            elif key == "g":
                self.pos = 0
            elif key in ("q",):
                print("\033[2J\033[H", end="")
                break
