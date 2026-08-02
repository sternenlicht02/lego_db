# LEGO_DB

A local application for searching and managing your LEGO collection
using the [Rebrickable](https://rebrickable.com/downloads/) catalog
dataset.

This project is **not affiliated with the LEGO Group**.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

* Local SQLite catalog, built from the Rebrickable dataset
* Prefix search by set number
* Owned-set tracking with condition and notes
* Related sets (same theme and year)
* Clipboard copy with set-number normalization
* Right-click to add/remove owned, `/` to focus search from anywhere
* Multi-language support (20 languages)
* Export/import of owned-set data (TXT + CSV)

## Requirements

* Python **3.10+** (standard library only -- no third-party runtime
  dependencies)

## Installation

### 1. Download the dataset

Download `sets.csv` and `themes.csv` from
[rebrickable.com/downloads](https://rebrickable.com/downloads/) and place
them in:

```
src/
└─ lego_db/
   └─ data/
      └─ csv/
         ├─ sets.csv
         └─ themes.csv
```

### 2. (Optional) Build or refresh the database manually

```
python scripts/build_db.py
```

Creates (or updates) the local catalog at `instance/lego_db.db`. Not
required for a first run -- only for refreshing an existing one against
newer CSV files.

### 3. Run the application

```
python legoDB.pyw
```

or double-click the file. On the very first run overall, a language
selection window appears; the choice is saved to `config.json`. If the
catalog is empty, a setup window then shows import progress for
`themes.csv` and `sets.csv` and stays open until you dismiss its
"Installation complete" message, after which the main window opens.

### Optional: install as a package

```
pip install -e .
```

```
python -m lego_db     # same as legoDB.pyw
lego-db                # console entry point
```

## Basic usage

### Search by set number prefix

```
123
```

Matches `123-1`, `1230-1`, and so on.

### View owned sets

```
owned
```

Filter by condition:

```
owned 0
owned 1
owned 2
```

### Quick focus shortcut

Press `/` to jump to the search box from anywhere in the window.

## Commands

Commands are entered directly into the search box.

| Command            | Meaning                      |
| ------------------ | ---------------------------- |
| `+0000-1`        | Add set to owned             |
| `-0000-1`        | Remove set from owned        |
| `2>0000-1`       | Set condition to 2           |
| `[note]>0000-1`  | Add a note                   |
| `2[note]>0000-1` | Set condition and add a note |
| `[note]2>0000-1` | Same as above                |

Multiple commands can be combined:

```
+1234-1 -5678-1 2[gift]>1111-1
```

Any unrecognized fragment anywhere in the text rejects the whole command
line -- nothing is applied. Set numbers may contain letters, digits, dots,
and dashes (e.g. `+100STORES-1`, `[note]>10213sup-1`), matching the full
range of formats found in the Rebrickable dataset.

### Context menu

Right-click a row to add or remove it from owned.

### Notes

Notes are written inside square brackets:

```
[Note]>1111-1
[2026. 01. 01. Gift]>1111-1
```

Escape `]` or `\` with a leading `\`:

```
[\]]>1234-1      -> ]
[a\]b]>1234-1    -> a]b
[a\\b]>1234-1    -> a\b
```

Control characters such as newline are not allowed anywhere in the input.

## Set details

Each set displays full catalog information, theme hierarchy, piece count,
release year, owned status, condition, and notes.

### Condition values

| Value | Meaning | Color       |
| ----- | ------- | ----------- |
| `0` | Default | Light Blue  |
| `1` | Bad     | Light Pink  |
| `2` | Good    | Light Green |

### Related sets

Selecting a set shows other sets sharing the same theme and year,
richest (most pieces) first.

## Clipboard

Copy from the quick-copy button or the detail dialog. Optional set-number
normalization reduces a set number to its base -- for example
`1308-1-DBASE-1` normalizes to `1308-1-DBASE` -- using the same rule the
app uses everywhere else to group variants of a set together (see
[Set-number format](#set-number-format) below).

Format:

```
<parent_theme> <theme> <set_num> <name>, <pieces>pc, <year>
```

## Export / import owned data

```
python scripts/export_owned.py
```

Writes `instance/exports/owned_<yymmdd>.txt` and `.csv`, where `yymmdd`
is the date the owned list was last added to -- not the date the export
itself runs. If nothing is owned yet, today's date is used. The `.txt`
file is a plain command-language script -- the same syntax described
above -- so it can also be pasted directly into the search box.

```
python scripts/import_owned.py
```

Restores owned-set data from the most recent `owned_<yymmdd>.txt` file
in `instance/exports/`. The restore is atomic: if anything goes wrong
partway through, the existing owned-set data is left completely
untouched rather than ending up cleared or half-restored.

## Set-number format

A set number is built only from ASCII letters, digits, `.`, and `-`, and
may contain more than one `-` (e.g. `1308-1-DBASE-1`, `214.10-1`,
`201908-mmb`). Its "base" is everything before the *last* `-`, provided
the text after that last `-` is made up only of digits; otherwise the
whole set number is its own base. This is the rule used for grouping
variants together, sorting search results, and the clipboard's
normalization option.

## Disclaimer

* **LEGO®** is a trademark of the LEGO Group.
* This project is **not affiliated with the LEGO Group**.
* Data is provided by **Rebrickable** and is not otherwise redistributed.

## AI usage disclosure

This project was developed with assistance from **ChatGPT (OpenAI)**
and **Claude (Anthropic)**. All final decisions and modifications were
reviewed by the project author.

## License

Licensed under the **MIT License**. See the `LICENSE` file for details.
