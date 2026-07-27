# Bulk File Organizer

A Python tool that sorts a messy folder of files into type-based subfolders, optionally adds a date prefix to filenames, and keeps a structured undo log so any sorting session can be fully reversed.

## What it does

- Recursively scans a folder for files
- Verifies each file's **real** type by inspecting its binary content (not just trusting the file extension), using the `filetype` library
- Flags files whose extension doesn't match their actual content as possibly corrupted or misnamed, and routes them to a separate `corrupted_files` folder for review
- Sorts everything else into type-based folders: `image_files`, `video_files`, `audio_files`, `document_files`, `archive_files`, `text_files`, `csv_files`, `office_files`, `json_files`, `python_files`, `markdown_files`, `other_files`
- Adds a `YYYY-MM-DD_` date prefix to filenames that don't already have one (based on the file's last-modified date)
- Shows a full **preview** of every planned move/rename before touching anything, and asks for confirmation
- Logs every action (and every skip/error) to a log file
- Records every successful move in a structured undo log, and can fully reverse an entire sorting session on request

## Requirements

- Python 3.9+
- `filetype` (see `requirements.txt`)

Install with:
```bash
pip install -r requirements.txt
```

## How to run

```bash
python bulk_file_organizer.py
```

You'll be prompted for:
1. The path to the folder containing the files you want organized
2. The path to the folder where sorted files, logs, and the undo log should be stored

The script will:
1. Scan and analyze all files
2. Show a full preview of what it plans to do — **nothing is moved yet**
3. Ask `Do you want to proceed with the sorting? (yes/no)` — only proceeds on `yes`
4. After sorting, ask `Do you want to undo the last sorting action? (yes/no)` — lets you immediately reverse the run if the result isn't what you expected

## Output

| File/Folder | Description |
|---|---|
| `image_files/`, `video_files/`, `audio_files/`, etc. | Category folders containing sorted files |
| `corrupted_files/` | Files whose real content didn't match their extension, or whose type couldn't be identified |
| `bulk_file_organizer_log.txt` | Full run log (timestamped actions, warnings, errors) |
| `undo_log.jsonl` | Structured record of every move made this session, used for undo |

## How undo works

Every successful move is written to `undo_log.jsonl` as a single JSON record, immediately after the move happens — so even if the script is interrupted partway through, everything moved so far is still safely undoable. Choosing "yes" to the undo prompt reverses every recorded move, most recent first, then clears the undo log.

## Error handling

The script fails gracefully with a clear message instead of crashing for common issues:
- Input folder doesn't exist
- Output folder can't be created (permissions, invalid path)
- `filetype` package not installed
- Files that are locked, in use, or inaccessible are skipped and logged, without stopping the rest of the run
- A destination file that already exists is skipped (never silently overwritten)

## Notes

- Filenames that already start with a date prefix (e.g. `2026-01-10_report.pdf`) are left alone and not re-prefixed.
- Because `filetype` identifies files by binary signature, plain-text-based formats (`.txt`, `.csv`, `.json`, `.md`, `.py`, etc.) can't be content-verified the same way images, PDFs, and office documents can — the script trusts the extension for these instead of flagging them as unverifiable.
- Console log output is currently disabled (file logging only). To also see live progress in the terminal, uncomment the `logging.StreamHandler()` line in the script.
