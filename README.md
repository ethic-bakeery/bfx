# bfx — Browser Forensic Explorer

> A command-line tool that turns raw browser databases into something a human can actually read and investigate.

---

## 📹 Video Demo

> **[Watch the demo on YouTube](https://youtu.be/-YhErNtPzFs)**

---

## Why I Built This

During a forensic investigation I was working on analysing browser activity as part of a case study on the Lazarus Group's Bybit crypto heist I had to dig through raw browser databases. Chrome keeps everything in SQLite files: your full browsing history, every search you typed, every file you downloaded, every password you saved. It's all there, sitting in plain files on disk.

I originally created [ethic-bakeery/sqlite-forensic-exporter](https://github.com/ethic-bakeery/sqlite-forensic-exporter) to help get data out of browser databases. It worked, but there was a catch: you still had to open every CSV file manually and hunt for what you needed one by one. In the middle of a real investigation, that’s just too slow.

**bfx** is the next step in that journey. I’ve rebuilt the engine and added a command-line interface so you can find your evidence without ever leaving the terminal. Instead of clicking through folders and spreadsheets, you get instant, searchable answers. It’s built to move as fast as the investigation does.

The problem? Opening those files is painful. You either import them into a spreadsheet tool and struggle with timestamps that look like `13341521924000000` (that's a real Chrome timestamp, by the way it means 2023-10-12 16:00:00 UTC), or you write SQL queries manually for every single question you want to answer. And if you're doing this in a professional context SOC analysis, incident response, a forensic investigation you end up doing the same repetitive work every single time.

So I built bfx. It's a tool I wished existed. You point it at a browser folder, it extracts everything, converts all the timestamps into readable dates, labels all the URLs, and then gives you a clean command-line interface to explore it all search across every table at once, filter by column, see the first or last rows, get a full session summary in seconds. No spreadsheet juggling, no SQL, no decoding timestamps by hand.

I built it as a learning project and a practical tool. If it helps other analysts, investigators, or students doing the same kind of work, that's what matters.

---

## What bfx Actually Does

Your browser is constantly writing data to SQLite database files on your computer. Chrome alone keeps:

- **History** —> every URL you visited, when you visited it, how many times
- **Downloads** —> every file you downloaded, where it came from, where it went
- **Searches** —> every query you typed into the address bar
- **Login Data** —> saved usernames and (encrypted) passwords
- **Autofill** —> every value you ever typed into a web form
- **Favicons** —> cached icons that can prove a site was visited even after history is cleared
- **Cookies** —> session data from every site

These files are stored in a folder on your computer and they're not going anywhere. `bfx export` reads all of them, converts everything into clean CSVs, and then `bfx` gives you a fast, readable terminal interface to investigate them.

---

## Requirements

- Python 3.8 or higher
- Windows, macOS, or Linux
- No external packages needed everything uses Python's standard library

---

## Installation

Download or clone the project, then run:

```bash
cd bfx
pip install -e .
```

That's it. The `bfx` command is now available anywhere in your terminal.

To confirm it installed correctly:

```bash
bfx --version
```

You should see: `bfx 1.0.0`

---

## The Two-Step Workflow

Everything in bfx follows the same pattern. First you export, then you explore.

### Step 1: Export

You point `bfx export` at your browser folder. It finds all the SQLite databases, extracts every table, converts timestamps, enriches URLs, and writes everything to a folder of CSVs.

```bash
bfx export --folder "C:\Articats"
```

This creates a `bfx_export` folder in your current directory. That folder is your **session** you'll point every other command at it.

### Step 2: Explore

Now you use `--session` to point bfx at that folder and run any command you like:

```bash
bfx --session bfx_export list
bfx --session bfx_export summary
bfx --session bfx_export search "lazarus"
```

That's the whole idea. Export once, explore as many times as you want without touching the original files.

---

## Browser Data Locations

If you want to export directly from the browser's live profile folder (rather than a copied folder), here are the paths:

| Browser | Windows |
|---------|---------|
| Chrome | `C:\Users\<you>\AppData\Local\Google\Chrome\User Data\Default` |
| Edge | `C:\Users\<you>\AppData\Local\Microsoft\Edge\User Data\Default` |
| Brave | `C:\Users\<you>\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default` |
| Firefox | `C:\Users\<you>\AppData\Roaming\Mozilla\Firefox\Profiles\<random>.default-release` |

| Browser | macOS |
|---------|-------|
| Chrome | `~/Library/Application Support/Google/Chrome/Default` |
| Edge | `~/Library/Application Support/Microsoft Edge/Default` |
| Safari | `~/Library/Safari/` |

**Note:** If the browser is currently open, some files will be locked. bfx handles this automatically by making a temporary copy before reading.

---

## Command Reference

### `export` Extract browser databases

This is always step one. It reads raw SQLite files and produces the CSV export that everything else works from.

```bash
# Export a copied browser folder (most common use case)
bfx export --folder "C:\Users\redacted\Desktop\Browser"

# Export to a specific output folder
bfx export --folder "C:\Users\redacted\Desktop\Browser" --output .\my_exports

# Export from a live Chrome profile
bfx export --folder "C:\Users\redacted\AppData\Local\Google\Chrome\User Data\Default" --output .\exports

# Export a single database file
bfx export --file "C:\Users\redacted\Desktop\Browser\History" --output .\exports

# Export only specific tables
bfx export --folder .\Browser --tables urls,visits,downloads

# Quick preview — only first 500 rows per table (good for large profiles)
bfx export --folder .\Browser --limit 500 --output .\preview

# Scan sub-folders too (useful for multi-profile Chrome installs)
bfx export --folder "C:\Users\redacted\AppData\Local\Google\Chrome\User Data" --recursive --output .\exports
```

**What it produces:**

```
bfx_export/
├── _FORENSIC_MANIFEST.csv       ← master index of everything exported
├── forensic_export.log          ← full run log with any errors
├── History/
│   ├── urls.csv
│   ├── visits.csv
│   ├── downloads.csv
│   └── keyword_search_terms.csv
├── Web_Data/
│   ├── autofill.csv
│   └── autofill_profiles.csv
└── Login_Data/
    └── logins.csv
```

---

### `list` See what was exported

After exporting, run this first. It shows you every table that was found, grouped by which database it came from, along with the alias you'll use to access it.

```bash
bfx --session bfx_export list
```

**Output:**

```
  Session Tables  (53 loaded, 12 skipped)
  ------------------------------------------------------------------------------

  Browsing History & Downloads
    ├─ cluster-keywords            698 rows   5 cols
    ├─ downloads                   410 rows  28 cols  Download history (files, sources, times)
    ├─ keyword-search-terms        201 rows   4 cols  Search queries typed by user
    ├─ urls                       9142 rows  11 cols  All visited URLs with visit counts and titles
    └─ visits                     9778 rows   8 cols  Individual page visit events with timestamps

  Autofill, Forms & Credit Cards
    ├─ autofill                    179 rows  10 cols  Autofill form field values
    └─ autofill-profiles            12 rows  22 cols  Saved name/address profiles

  Saved Passwords (Hashed)
    └─ logins                       45 rows  10 cols  Saved login credentials (passwords encrypted)

  Total: 53 tables  |  28,441 rows across all tables

  1 empty/unreadable table(s) not shown above.
  Full list written to: skipped_tables.txt
```

The name on the left of each line — `urls`, `downloads`, `logins`, `visits` — is the **alias**. That's what you use in every other command. Empty tables don't clutter your screen; they get quietly written to `skipped_tables.txt` so you can check them if needed.

---

### `head` and `tail`  Quick look at rows

The fastest way to see what's in a table. `head` shows the first N rows, `tail` shows the last N.

```bash
# First 20 downloads
bfx --session bfx_export head downloads --rows 20

# Last 10 visits
bfx --session bfx_export tail visits --rows 10

# First 50 search queries
bfx --session bfx_export head keyword-search-terms --rows 50

# First 5 saved logins
bfx --session bfx_export head logins --rows 5
```

**Output for `head downloads --rows 1`:**

```
  first 1 rows  of  downloads  ·  Download history (files, sources, times)

  Record 1
  --------------------------------------------------------------------------------------
    id           1
    target_path  C:/Users/test/Downloads/report.pdf
    tab_url      https://github.com/report.pdf
                     -> github.com | HTTPS
    total_bytes  512000
    mime_type    application/pdf
    danger_type  0
    start_time   13341600000000000
                     -> 2023-10-12 16:00:00 UTC | (WebKit (Chrome))

  1 record(s)
```

Wide tables — like `downloads` which has 28 columns automatically display as vertical cards so nothing gets squashed. The `->` lines are enrichment values bfx added: the domain extracted from the URL, the URL category, and the timestamp converted to a readable date.

---

### `view` Browse a full table with pagination

When you want to page through an entire table rather than just a preview.

```bash
bfx --session bfx_export view urls
```

Navigate with: **SPACE** = next page, **B** = previous page, **Q** = quit.

```bash
# Show first 100 rows without pagination
bfx --session bfx_export view urls --rows 100

# Save the entire table to a new CSV
bfx --session bfx_export view logins --export logins_review.csv

# Output as JSON (great for piping to other tools)
bfx --session bfx_export view urls --json
```

---

### `search` Find anything across all tables at once

This is probably the command you'll use most during an investigation. You give it a keyword and it scans every single table simultaneously, then groups the results by table so you can see exactly where each hit came from.

```bash
bfx --session bfx_export search "lazarus"
```

**Output:**

```
  Search results for  "lazarus"  — 5 hit(s) across 4 table(s)
  ------------------------------------------------------------------------------

  ┌─ autofill  [Autofill form field values]  1 hit(s)
  Record 1
  --------------------------------------------------------------------------------------
    name            search
    value           lazarus group
    date_created    13341600000000000
                        -> 2023-10-12 16:00:00 UTC | (WebKit (Chrome))

  ┌─ cluster-keywords  [cluster_keywords]  1 hit(s)
  cluster_id  keyword                    type    score
  ----------  -------------------------  ------  ------
  11          lazarus anime hacking pic  4       100

  ┌─ downloads  [Download history (files, sources, times)]  1 hit(s)
  Record 1
  --------------------------------------------------------------------------------------
    id           2
    target_path  C:/Users/test/Downloads/lazarus_analysis.zip
    tab_url      https://malware-site.ru/payload.zip
                     -> malware-site.ru | HTTP
    danger_type  1
    start_time   13341800000000000
                     -> 2023-10-14 09:00:00 UTC | (WebKit (Chrome))

  ┌─ keyword-search-terms  [Search queries typed by user]  1 hit(s)
  url_id  lower_term                                  term
  ------  ------------------------------------------  ------------------------------------------
  1       lazarus group bybit crypto heist case study  Lazarus Group Bybit Crypto Heist Case Study

  Tip: add  --export hits.csv  to save all 5 hits.
```

More search options:

```bash
# Narrow to a single table
bfx --session bfx_export search "github" --table logins

# Search within one specific column
bfx --session bfx_export search "pdf" --col mime_type

# Case-sensitive search
bfx --session bfx_export search "Lazarus" --case

# Save every hit to a single CSV
bfx --session bfx_export search "lazarus" --export lazarus_hits.csv

# Output as JSON (pipeable to jq, Python, etc.)
bfx --session bfx_export search "lazarus" --json

# Limit results per table (useful for very large result sets)
bfx --session bfx_export search "google" --rows 20
```

---

### `filter` Show only rows matching a condition

Where `search` is a broad keyword scan, `filter` is precise. You pick a column and a value, and it returns only the rows that match.

```bash
# Show only HTTPS URLs
bfx --session bfx_export filter urls --col url__CATEGORY --value HTTPS

# Show only dangerous downloads (danger_type is not 0)
bfx --session bfx_export filter downloads --col danger_type --value "^[^0]" --regex

# Show all .zip downloads
bfx --session bfx_export filter downloads --col mime_type --value zip

# Multiple conditions — AND logic (zip files from HTTP sources)
bfx --session bfx_export filter downloads --col mime_type            --value zip \
                                          --col tab_url__CATEGORY    --value HTTP

# Use a regex for partial matching
bfx --session bfx_export filter urls --col url --value "^https://g" --regex

# Save the filtered result
bfx --session bfx_export filter downloads --col danger_type --value 1 \
                                          --export dangerous_downloads.csv
```

**Output for `filter urls --col url__CATEGORY --value HTTPS`:**

```
  urls  filter: url__CATEGORY=HTTPS  ·  3 match(es)

  Record 1
  --------------------------------------------------------------------------------------
    id               1
    url              https://google.com
                         -> google.com | HTTPS
    title            Google
    visit_count      50
    last_visit_time  13341521924000000
                         -> 2023-10-11 18:18:44 UTC | (WebKit (Chrome))

  Record 2
  --------------------------------------------------------------------------------------
    id               2
    url              https://github.com
                         -> github.com | HTTPS
    ...

  3 record(s)
```

---

### `summary` Session overview in seconds

The first thing to run when you open a new case. Gives you the full picture: all tables and row counts, the date range of activity, top visited domains, top search queries, and download breakdown.

```bash
bfx --session bfx_export summary
```

**Output:**

```
  Forensic Session Summary
  ------------------------------------------------------------------------------

  📂  Table Inventory
  Alias                 Source Database                 Rows
  --------------------  ------------------------------  ------
  autofill              Autofill, Forms & Credit Cards  179
  downloads             Browsing History & Downloads    410
  keyword-search-terms  Browsing History & Downloads    201
  urls                  Browsing History & Downloads    9142
  visits                Browsing History & Downloads    9778
  logins                Saved Passwords (Hashed)        45

  🕐  Activity Date Range
  [i]  Earliest visit : 2023-10-11 18:18:44 UTC
  [i]  Latest   visit : 2023-10-15 02:40:00 UTC
  [i]  Total  visits  : 9778

  🌐  Top 10 Visited Domains
  Domain           Count
  ---------------  ------
  google.com       312
  github.com       87
  reddit.com       54
  malware-site.ru  3

  🔍  Top 10 Search Queries
  Search Term                            Count
  -------------------------------------  ------
  lazarus group bybit crypto heist       8
  bybit hacked executive summary         5
  soc analyst internship uae             4
  tryhackme                              3

  ⬇  Downloads
  [i]  Total files : 410
  MIME Type             Count
  --------------------  ------
  application/pdf       201
  application/zip       87
  application/msword    34
```

---

### `schema` — Inspect a table's columns

When you need to know what columns a table has before filtering or searching, `schema` gives you the full picture: column names, whether bfx added them as enrichment, how many non-empty values there are, and sample values from the data.

```bash
bfx --session bfx_export schema visits
bfx --session bfx_export schema logins --samples 5
```

**Output:**

```
  Schema — logins  ·  Saved login credentials (passwords encrypted)
  ------------------------------------------------------------------------------
  [i]  Source DB  : Saved Passwords (Hashed)
  [i]  Total rows : 45  (source DB had 45)
  [i]  Exported   : 2026-04-01 15:25:32 UTC   MD5: deadbeefdeadbeef

  #       Column                 Kind      Non-empty  Unique  Top 3 values
  ------  ---------------------  --------  ---------  ------  ----------------------------------
  1       id                     original  45         45      1  |  2  |  3
  2       origin_url             original  45         38      https://github.com  |  ...
  3       username_value         original  45         12      analyst_analyst  |  analyst  |  ...
  4       password_value         original  45         1       <BLOB: encrypted>
  7       date_created__HUMAN    enriched  45         38      2023-10-11 18:18:44 UTC  |  ...
  8       date_created__FORMAT   enriched  45         1       WebKit (Chrome)
  9       origin_url__DOMAIN     enriched  45         38      github.com  |  tryhackme.com  |  ...
  10      origin_url__CATEGORY   enriched  45         1       HTTPS
```

Columns marked `enriched` were added by bfx they didn't exist in the original database. Columns marked `original` are from the raw SQLite file exactly as Chrome stored them.

---

### `info` Forensic metadata for a table

Shows provenance information for chain-of-custody documentation: where the data came from, the MD5 hash of the source file, when it was exported, and the full column list.

```bash
bfx --session bfx_export info logins
bfx --session bfx_export info downloads
```

**Output:**

```
  Table Info — logins
  ------------------------------------------------------------------------------
  Alias:                       logins
  Table name:                  logins
  Description:                 Saved login credentials (passwords encrypted)

  Source database:             C:\Users\redacted\Desktop\Browser\Login Data
  DB description:              Saved Passwords (Hashed)

  Rows (this export):          45
  Rows in source DB:           45
  Columns:                     10

  Export timestamp:            2026-04-01 15:25:32 UTC
  MD5 (source DB):             deadbeefdeadbeef1234567890abcdef
  CSV file:                    bfx_export\Login_Data\logins.csv

  Columns:
      1.  id
      2.  origin_url
      3.  username_value
      4.  password_value
      5.  date_created
      6.  times_used
      7.  date_created__HUMAN    [enriched]
      8.  date_created__FORMAT   [enriched]
      9.  origin_url__DOMAIN     [enriched]
     10.  origin_url__CATEGORY   [enriched]
```

---

## Understanding the Enrichment Columns

One of the more useful things bfx does automatically is add extra columns alongside timestamp and URL columns. Chrome stores timestamps as large integers and doesn't label URLs by protocol bfx adds readable versions of both.

Here's what gets added:

| Original column | Added by bfx | Example value |
|---|---|---|
| `last_visit_time` | `last_visit_time__HUMAN` | `2023-10-11 18:18:44 UTC` |
| | `last_visit_time__FORMAT` | `WebKit (Chrome)` |
| `url` | `url__DOMAIN` | `google.com` |
| | `url__CATEGORY` | `HTTPS` / `HTTP` / `Extension` / `Local File` |
| `start_time` | `start_time__HUMAN` | `2023-10-14 09:00:00 UTC` |
| `tab_url` | `tab_url__DOMAIN` | `malware-site.ru` |
| | `tab_url__CATEGORY` | `HTTP` |

In the terminal output, enrichment values show up as `->` lines directly below the raw value:

```
  tab_url      https://malware-site.ru/payload.zip
                   -> malware-site.ru | HTTP
  start_time   13341800000000000
                   -> 2023-10-14 09:00:00 UTC | (WebKit (Chrome))
```

You don't have to remember which timestamp format Chrome uses. bfx handles five different formats — WebKit microseconds, Unix seconds, Unix milliseconds, Apple Cocoa, and PRTime — and auto-detects the right one.

---

## Timestamp Formats (for reference)

If you ever need to convert a raw timestamp yourself:

| Format | Used by | Raw example | Readable |
|---|---|---|---|
| WebKit (microseconds since 1601-01-01) | Chrome, Edge, Brave | `13341521924000000` | `2023-10-11 18:18:44 UTC` |
| Unix seconds | Firefox, some Chrome tables | `1697047124` | `2023-10-11 18:18:44 UTC` |
| Unix milliseconds | Some web APIs | `1697047124000` | `2023-10-11 18:18:44 UTC` |
| Apple Cocoa (seconds since 2001-01-01) | Safari | `718481924` | `2023-10-11 18:18:44 UTC` |

bfx converts all of these automatically. The `__FORMAT` column tells you which one it detected.

---

## Output Modes

Every command supports two output modes beyond the default terminal display.

### JSON output

Add `--json` to any command to get machine-readable JSON. Good for piping to `jq`, writing scripts, or feeding results into other tools.

```bash
bfx --session bfx_export view urls --json
bfx --session bfx_export search "lazarus" --json
bfx --session bfx_export summary --json
bfx --session bfx_export head logins --rows 10 --json
```

Example with `jq`:

```bash
# Get all unique domains visited
bfx --session bfx_export view urls --json | jq '.[].url__DOMAIN' | sort -u

# Count downloads by mime type
bfx --session bfx_export view downloads --json | jq 'group_by(.mime_type) | map({type: .[0].mime_type, count: length})'
```

### Export to file

Add `--export filename.csv` (or `.json`) to save results to a file instead of (or in addition to) displaying them.

```bash
# Save search results
bfx --session bfx_export search "lazarus" --export lazarus_investigation.csv

# Save a filtered view
bfx --session bfx_export filter downloads --col danger_type --value 1 --export flagged_downloads.csv

# Save a full table
bfx --session bfx_export view logins --export logins_full.csv

# Save as JSON
bfx --session bfx_export search "password" --export password_hits.json
```

---

## Practical Investigation Examples

### "What sites did this user visit in the last week?"

```bash
# Get the full URL history sorted by last visit
bfx --session bfx_export view urls --rows 100

# Or filter to HTTPS only (which removes most browser internal pages)
bfx --session bfx_export filter urls --col url__CATEGORY --value HTTPS
```

### "Did this user search for anything suspicious?"

```bash
# See all search queries
bfx --session bfx_export head keyword-search-terms --rows 100

# Search for a specific term across everything
bfx --session bfx_export search "north korea"
bfx --session bfx_export search "how to"
```

### "What files did this user download?"

```bash
# All downloads
bfx --session bfx_export view downloads

# Only dangerous downloads (Chrome flagged these)
bfx --session bfx_export filter downloads --col danger_type --value "^[^0]" --regex

# Only zip files
bfx --session bfx_export filter downloads --col mime_type --value zip

# Downloads from HTTP (unencrypted) sources — worth investigating
bfx --session bfx_export filter downloads --col tab_url__CATEGORY --value HTTP
```

### "What accounts does this user have saved?"

```bash
# All saved credentials (usernames are plain text, passwords are encrypted)
bfx --session bfx_export view logins

# Check what domains have saved logins
bfx --session bfx_export schema logins --samples 20
```

### "I want to investigate a specific domain across everything"

```bash
# Search for any reference to that domain across all tables
bfx --session bfx_export search "github.com" --export github_activity.csv
bfx --session bfx_export search "malware-site.ru"
```

### "I need to document this for a report"

```bash
# Get forensic metadata with MD5 hashes for chain of custody
bfx --session bfx_export info urls
bfx --session bfx_export info downloads
bfx --session bfx_export info logins

# Export everything you need as CSV
bfx --session bfx_export view urls --export evidence_urls.csv
bfx --session bfx_export view downloads --export evidence_downloads.csv
bfx --session bfx_export search "keyword" --export keyword_hits.csv
```

---

## The Skipped Tables File

When you run `bfx list`, any table that has zero rows is excluded from the terminal output to keep things clean. Instead, bfx writes a file called `skipped_tables.txt` to your current directory. You can open that file to see everything that was skipped and why.

Example `skipped_tables.txt`:

```
BFX — Skipped / Empty Tables
============================================================
These tables were excluded from the terminal output
because they contained no data rows.

Alias                                     Reason                          Source Table
----------------------------------------------------------------------------------------------------
autofill-model-type-state                 table is empty (0 data rows)    autofill_model_type_state
meta                                      table is empty (0 data rows)    meta in Browsing History
segments                                  table is empty (0 data rows)    segments in History
```

---

## Colour Output

bfx uses colour output automatically when it detects a supported terminal. It's smart about this — it won't try to use colour in Windows CMD (where ANSI codes print as raw characters), but it will use it in Windows Terminal, PowerShell with colour support, VS Code's integrated terminal, and all Unix terminals.

To disable colour output manually:

```bash
bfx --no-color --session bfx_export list
```

Or set it as an environment variable so you never have to type it:

```bash
# Windows CMD
set NO_COLOR=1

# PowerShell
$env:NO_COLOR = "1"

# Linux / macOS
export NO_COLOR=1
```

---

## All Global Options

These go before the subcommand:

```bash
bfx --session <path>   # path to your bfx_export folder (required for all except export)
bfx --no-color         # disable ANSI colour
bfx --version          # print version
bfx --help             # show help
```

---

## Full Help for Every Command

Each command has its own `--help` with all options listed:

```bash
bfx --help
bfx export  --help
bfx list    --help
bfx view    --help
bfx head    --help
bfx tail    --help
bfx search  --help
bfx filter  --help
bfx schema  --help
bfx info    --help
bfx summary --help
```

---

## Project Structure

For anyone who wants to extend the tool or understand how it's built:

```
bfx/
├── pyproject.toml                  ← pip package config
├── README.md
└── bfx/
    ├── cli.py                      ← entry point, command routing
    ├── core/
    │   ├── session.py              ← loads export folder, builds alias registry
    │   ├── exporter.py             ← shared CSV/JSON export utility
    │   └── exporter_engine.py      ← the SQLite extraction engine
    ├── ui/
    │   └── terminal.py             ← all rendering: tables, cards, pagination, colour
    └── commands/
        ├── cmd_export.py           ← bfx export
        ├── cmd_list.py             ← bfx list
        ├── cmd_view.py             ← bfx view
        ├── cmd_head_tail.py        ← bfx head / bfx tail
        ├── cmd_search.py           ← bfx search
        ├── cmd_filter.py           ← bfx filter
        ├── cmd_schema.py           ← bfx schema
        ├── cmd_summary.py          ← bfx summary
        └── cmd_info.py             ← bfx info
```

Adding a new command takes three steps: create `commands/cmd_newname.py` with a `run()` function and a `HELP` string, add it to `commands/__init__.py`, and register it in `cli.py`. Nothing else needs to change.

---

## Known Limitations

- **Passwords are not decrypted.** Chrome encrypts saved passwords using Windows DPAPI (or macOS Keychain). bfx exports the encrypted blob so you can see that a credential exists and when it was saved, but not the password itself. Decryption requires separate tooling and the user's OS credentials.
- **Incognito sessions don't leave history rows**, but they may still leave favicon cache entries, DNS cache entries, and crash dump data. bfx exports whatever is on disk — it can't recover what was never written.
- **Deleted records are not recovered.** When a user clears their browser history, Chrome deletes the rows from the SQLite database. The space is marked as free and may still contain recoverable data, but bfx reads live rows only. For deleted record recovery, use a dedicated SQLite carving tool alongside bfx.
- **Firefox support is partial.** The export engine reads any SQLite file it finds, so Firefox databases will export. However, Firefox uses slightly different table names and timestamp formats. The enrichment logic is optimised for Chromium-based browsers.

---

## Supported Browsers

| Browser | Status |
|---------|--------|
| Google Chrome | Full support |
| Microsoft Edge | Full support |
| Brave | Full support |
| Opera | Full support |
| Vivaldi | Full support |
| Firefox | Partial exports work, some enrichment may not apply |
| Safari | Partial History.db exports; Cookies.binarycookies not supported |

---

## Contributing

If you find a bug, have a table or browser that isn't working right, or want to add a new command open an issue or a pull request. The codebase is intentionally simple and modular so it's easy to extend.

---

## License

MIT — use it however you like.

---

*Built during an investigation into browser forensic artifacts. If it saves you time on your next case, that's the whole point.*
