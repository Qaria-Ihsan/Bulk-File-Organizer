import shutil, sys, re, os, json, argparse, logging
from pathlib import Path
from datetime import datetime as dt

try:
    import filetype
except ImportError:
    print("Error: the 'filetype' package is required but not installed.")
    print("Install it with: pip install filetype")
    sys.exit(1)

TEXT_LIKE_EXTENSIONS = {".txt", ".csv", ".json", ".md", ".py", ".log", ".ini", ".yaml", ".yml"}

EXTENSION_ALIASES = {".jpeg": ".jpg"}


def normalize_ext(ext):
    return EXTENSION_ALIASES.get(ext, ext)


inputfolder = input("Enter the location of Messy File's folder : ")
outputfolder = input("Enter the location where you want to store the new folders : ")

if not os.path.exists(inputfolder):
    print(f"Error: Input folder '{inputfolder}' does not exist.")
    sys.exit(1)

try:
    Path(outputfolder).mkdir(parents=True, exist_ok=True)
    print("Checking if the output folder exists, if not, creating one.")
except PermissionError as e:
    print(f"Cannot create output folder '{outputfolder}': permission denied: {e}")
    sys.exit()
except OSError as e:
    print(f"Cannot create output folder '{outputfolder}': {e}")
    sys.exit()

log_file = os.path.join(outputfolder, 'bulk_file_organizer_log.txt')
undo_log_file = os.path.join(outputfolder, 'undo_log.jsonl')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        #logging.StreamHandler() # uncomment this line if you want to see logs in the console as well.
    ]
)

logging.info("Starting file organization process")
logging.info(f"Input folder: {inputfolder}")
logging.info(f"Output folder: {outputfolder}")


def scan_folder(inputfolder):
    inputfolder = Path(inputfolder)
    files_info = []
    for file in inputfolder.rglob("*"):
        if file.is_file():
            claimed_extension = file.suffix.lower()
            kind = filetype.guess(file)

            if kind:
                real_extension = "." + kind.extension
                mime_type = kind.mime
            elif claimed_extension in TEXT_LIKE_EXTENSIONS:
                real_extension = claimed_extension
                mime_type = "text/plain"
            else:
                real_extension = "Unknown"
                mime_type = "Unknown"

            file_info = {
                "name": file.name,
                "original_path": str(file),
                "size": file.stat().st_size,
                "claimed_extension": claimed_extension,
                "real_extension": real_extension,
                "mime_type": mime_type,
                "modified_time": dt.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            }
            files_info.append(file_info)
    logging.info(f"Scanned {len(files_info)} files from {inputfolder}")
    return files_info


def plan_sort(files_info, outputfolder):
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_")

    for i, file in enumerate(files_info):
        files_info[i]["Rename"] = "No"

        if file["real_extension"] == "Unknown":
            files_info[i]["Action"] = "corrupted_files"
            files_info[i]["dest_path"] = os.path.join(outputfolder, "corrupted_files", file["name"])
            logging.warning(f"File '{file['name']}' has unrecognized type (possibly corrupted)")
            continue

        if normalize_ext(file["claimed_extension"]) != normalize_ext(file["real_extension"]):
            files_info[i]["Action"] = "corrupted_files"
            files_info[i]["dest_path"] = os.path.join(outputfolder, "corrupted_files", file["name"])
            logging.warning(
                f"File '{file['name']}' extension mismatch: "
                f"claimed {file['claimed_extension']}, actual {file['real_extension']}"
            )
            continue

        mo = date_pattern.match(file["name"])
        if not mo:
            newname = f"{file['modified_time'].split(' ')[0]}_{file['name']}"
            files_info[i]["Rename"] = newname

        if file["real_extension"] in [".jpg", ".jpeg", ".png", ".gif"]:
            category = "image_files"
        elif file["real_extension"] in [".mp4", ".avi", ".mov"]:
            category = "video_files"
        elif file["real_extension"] in [".mp3", ".wav", ".flac"]:
            category = "audio_files"
        elif file["real_extension"] == ".pdf":
            category = "document_files"
        elif file["real_extension"] in [".zip", ".rar", ".7z"]:
            category = "archive_files"
        elif file["real_extension"] == ".txt":
            category = "text_files"
        elif file["real_extension"] == ".csv":
            category = "csv_files"
        elif file["real_extension"] in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]:
            category = "office_files"
        elif file["real_extension"] == ".json":
            category = "json_files"
        elif file["real_extension"] in [".py", ".ipynb"]:
            category = "python_files"
        elif file["real_extension"] == ".md":
            category = "markdown_files"
        else:
            category = "other_files"
            logging.debug(f"File '{file['name']}' with extension {file['real_extension']} categorized as 'other_files'")

        files_info[i]["Action"] = category
        files_info[i]["dest_path"] = os.path.join(outputfolder, category, file["name"])

    return files_info


def preview(files_info):
    print("Preview of the planned sorting:")
    total_files = len(files_info)
    corrupted_count = 0
    renamed_count = 0

    for file in files_info:
        print("-----------------------------")
        print(f"File current name: {file['name']}")
        print(f"  Current Path: {file['original_path']}")
        print(f"  Category: {file.get('Action', 'Unknown')}")
        print(f"  Will move to: {file['dest_path']}")

        if file.get("Action") == "corrupted_files":
            corrupted_count += 1
            print("  [WARNING: File is corrupted or misclassified]")

        if file["Rename"] != "No":
            print(f"  Will rename to: {file['Rename']}")
            renamed_count += 1
        else:
            print("  Will not rename.")

    print("-----------------------------")
    print(f"Total files: {total_files}")
    print(f"Files to be renamed: {renamed_count}")
    print(f"Corrupted/unrecognized files detected: {corrupted_count}")
    logging.info(f"Preview complete: {total_files} files, {renamed_count} to rename, {corrupted_count} corrupted/unrecognized")


def execute_actions(files_info, outputfolder, undo_log_file):
    action_types = {
        "corrupted_files", "image_files", "video_files", "audio_files",
        "document_files", "archive_files", "text_files", "csv_files",
        "office_files", "json_files", "python_files", "markdown_files", "other_files"
    }

    with open(undo_log_file, "a", encoding="utf-8") as undo_log:
        for file in files_info:
            action = file.get("Action")
            if action not in action_types:
                logging.warning(f"Skipping '{file['name']}': unknown action '{action}'")
                continue

            target_folder = os.path.join(outputfolder, action)

            try:
                Path(target_folder).mkdir(parents=True, exist_ok=True)

                final_name = file["Rename"] if file["Rename"] != "No" else file["name"]
                new_file_path = os.path.join(target_folder, final_name)

                if os.path.exists(new_file_path):
                    logging.warning(f"File already exists at '{new_file_path}'. Skipping '{file['name']}'")
                    continue

                shutil.move(file["original_path"], new_file_path)
                logging.info(f"Moved '{file['original_path']}' to '{new_file_path}'")

                undo_record = {
                    "timestamp": dt.now().isoformat(),
                    "original_path": file["original_path"],
                    "new_path": new_file_path
                }
                undo_log.write(json.dumps(undo_record) + "\n")
                undo_log.flush()

                if file["Rename"] != "No":
                    logging.info(f"Renamed to '{file['Rename']}'")

            except FileNotFoundError as e:
                logging.error(f"File not found: '{file['original_path']}': {e}")
            except PermissionError as e:
                logging.error(f"Permission denied moving '{file['original_path']}': {e}")
            except shutil.Error as e:
                logging.error(f"Error moving '{file['original_path']}': {e}")
            except Exception:
                logging.exception(f"Failed to move '{file['original_path']}'")


def undo_from_log(undo_log_file):
    if not os.path.exists(undo_log_file):
        print(f"Undo log '{undo_log_file}' does not exist. Nothing to undo.")
        logging.warning("Attempted to undo but undo log file not found")
        return

    records = []
    try:
        with open(undo_log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    logging.warning(f"Skipping malformed undo log line: {line}")
    except IOError as e:
        logging.error(f"Failed to read undo log file: {e}")
        return

    if not records:
        print("No file moves found in the undo log.")
        logging.info("Undo requested but no records found")
        return

    print(f"Found {len(records)} file(s) to undo...")
    for record in reversed(records):
        source = record["new_path"]
        destination = record["original_path"]
        try:
            if os.path.exists(source):
                Path(destination).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(source, destination)
                logging.info(f"Undo: Moved '{source}' back to '{destination}'")
            else:
                logging.warning(f"Undo: File not found at '{source}', cannot restore to '{destination}'")
        except FileNotFoundError as e:
            logging.error(f"File not found during undo: {e}")
        except PermissionError as e:
            logging.error(f"Permission denied during undo: {e}")
        except shutil.Error as e:
            logging.error(f"Error moving file during undo: {e}")
        except Exception:
            logging.exception("Failed to undo move")

    try:
        os.remove(undo_log_file)
        logging.info("Undo log cleared after successful undo.")
    except OSError as e:
        logging.warning(f"Could not remove undo log after undo: {e}")


scanned_files = scan_folder(inputfolder)

if not scanned_files:
    print("No files found in the input folder.")
    logging.warning("No files found to organize")
    sys.exit(0)

planned_files = plan_sort(scanned_files, outputfolder)
preview(planned_files)

answer = input("Do you want to proceed with the sorting? (yes/no): ")
if answer.lower() == "yes":
    logging.info("User confirmed to proceed with sorting")
    execute_actions(planned_files, outputfolder, undo_log_file)
    print("Sorting completed. Check the log file for details.")
    logging.info("Sorting completed successfully")
elif answer.lower() == "no":
    print("Sorting cancelled by user.")
    logging.info("User cancelled sorting")
    sys.exit(0)
else:
    print("Invalid input. Please enter 'yes' or 'no'.")
    logging.warning(f"Invalid input from user: {answer}")
    sys.exit(1)

while True:
    undo = input("Do you want to undo the last sorting action? (yes/no): ")
    if undo.lower() == "yes":
        logging.info("User requested undo")
        undo_from_log(undo_log_file)
        print("Undo completed. Check the log file for details.")
        logging.info("Undo operation completed")
        break
    elif undo.lower() == "no":
        print("No undo requested.")
        logging.info("User chose not to undo")
        break
    else:
        print("Invalid input. Please enter 'yes' or 'no'.")
        logging.warning(f"Invalid undo input from user: {undo}")

logging.info("File organization process completed")
print("Process finished. Thank you for using Bulk File Organizer!")