# consolidate_code.py
import argparse
import pathlib
import sys

DEFAULT_OUTPUT_FILENAME = "output.txt"
DEFAULT_INCLUDE_PATTERNS = {
    "/Users/steveswalker/code/ca-api-quickstarts/quickstart-v2/terraform/cloud_run.tf",
    "/Users/steveswalker/code/ca-api-quickstarts/quickstart-v2/terraform/firestore.tf",
    "/Users/steveswalker/code/ca-api-quickstarts/quickstart-v2/terraform/main.tf",
    "//Users/steveswalker/code/ca-api-quickstarts/quickstart-v2/terraform/secrets.tf",
}

ALWAYS_EXCLUDE_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".git",
    ".vscode",
}
# ---------------------


def consolidate_code(root_dir, include_patterns=DEFAULT_INCLUDE_PATTERNS):
    """
    Finds all .py files matching the include patterns within a directory tree,
    reads them, and consolidates their content into a single string
    with clear file separators.

    Args:
        root_dir (str or pathlib.Path): The root directory of the project.
        include_patterns (set): A set of strings representing files or directories
                                 (with trailing slash) to include.

    Returns:
        tuple: (consolidated_content_string, list_of_processed_files)
    """
    root_path = pathlib.Path(root_dir).resolve()
    consolidated_content = []
    processed_files = []
    processed_files_paths = set()  # Keep track of full paths to avoid duplicates

    if not root_path.is_dir():
        print(f"Error: Root directory not found: {root_path}", file=sys.stderr)
        return "", []

    print(f"Scanning directory: {root_path}", file=sys.stderr)
    print(f"Including patterns: {', '.join(sorted(include_patterns))}", file=sys.stderr)
    print(
        f"Always excluding subdirs named: {', '.join(sorted(ALWAYS_EXCLUDE_DIRS))}",
        file=sys.stderr,
    )
    print("-" * 30, file=sys.stderr)

    for pattern in sorted(list(include_patterns)):  # Sort for consistent order
        item_path = root_path / pattern

        if not item_path.exists():
            print(
                f"Warning: Include pattern path not found: {item_path}", file=sys.stderr
            )
            continue

        files_to_process = []
        if item_path.is_file():
            # If the pattern is a specific file
            if item_path.suffix == ".py":
                files_to_process.append(item_path)
            else:
                print(
                    f"Warning: Included file is not a .py file, skipping: {item_path.relative_to(root_path)}",
                    file=sys.stderr,
                )
        elif item_path.is_dir():
            # If the pattern is a directory (ends with / handled by pathlib)
            # Recursively find all .py files within this directory
            for py_file in item_path.rglob("*.py"):
                # Check if the file is within an always excluded directory
                is_in_excluded_dir = False
                # Check parts relative to the *included* directory base first
                relative_to_included_dir = py_file.relative_to(item_path)
                for part in relative_to_included_dir.parts:
                    if part in ALWAYS_EXCLUDE_DIRS:
                        is_in_excluded_dir = True
                        break
                if not is_in_excluded_dir:
                    for part in py_file.relative_to(root_path).parts:
                        if part in ALWAYS_EXCLUDE_DIRS:
                            is_in_excluded_dir = True
                            break

                if not is_in_excluded_dir:
                    files_to_process.append(py_file)

        for file_path in files_to_process:
            if file_path not in processed_files_paths:
                relative_path = file_path.relative_to(root_path)
                processed_files_paths.add(file_path)
                processed_files.append(str(relative_path))
                print(f"Adding file: {relative_path}", file=sys.stderr)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    consolidated_content.append(
                        f"# --- START FILE: {relative_path} ---"
                    )
                    consolidated_content.append(content)
                    consolidated_content.append(
                        f"# --- END FILE: {relative_path} ---\n\n"
                    )

                except UnicodeDecodeError:
                    print(
                        f"Warning: Could not decode file {relative_path} as UTF-8. Skipping.",
                        file=sys.stderr,
                    )
                except IOError as e:
                    print(
                        f"Warning: Could not read file {relative_path}: {e}",
                        file=sys.stderr,
                    )
                except Exception as e:
                    print(
                        f"Warning: An unexpected error occurred processing {relative_path}: {e}",
                        file=sys.stderr,
                    )

    print("-" * 30, file=sys.stderr)

    processed_files.sort()
    return "".join(consolidated_content), processed_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Consolidate Python code from specified files/directories into a single block.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "root_dir",
        nargs="?",
        default=".",
        help="The root directory of your project (default: current directory).",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        # Default value is now handled in the logic below, not in add_argument
        help=f"Optional: Write the consolidated code to the specified file (default: {DEFAULT_OUTPUT_FILENAME}).",
    )
    parser.add_argument(
        "--include",
        action="append",
        metavar="PATH",
        help=f"Specify a file or directory (end with '/') to include. Use multiple times. Overrides default includes. If not used, defaults are: {', '.join(sorted(DEFAULT_INCLUDE_PATTERNS))}",
    )

    args = parser.parse_args()

    current_include_patterns = set()
    if args.include:
        current_include_patterns.update(args.include)
        print(f"Using command-line include patterns.", file=sys.stderr)
    else:
        current_include_patterns = DEFAULT_INCLUDE_PATTERNS.copy()
        print(f"Using default include patterns.", file=sys.stderr)

    combined_code, files_processed = consolidate_code(
        args.root_dir, include_patterns=current_include_patterns
    )

    if files_processed:
        # --- Modified output logic ---
        # Determine the target filename: use provided -o or the default
        target_output_file = args.output if args.output else DEFAULT_OUTPUT_FILENAME

        try:
            output_path = pathlib.Path(target_output_file)
            # Ensure parent directory exists before writing
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f_out:
                f_out.write(combined_code)
            # Always report the file it was written to
            print(
                f"Consolidated code for {len(files_processed)} files written to: {output_path}",
                file=sys.stderr,
            )
        except IOError as e:
            print(
                f"Error: Could not write to output file {target_output_file}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        except Exception as e:
            print(
                f"Error: An unexpected error occurred writing to file {target_output_file}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
        # --- End of modified output logic ---

        # Print summary information to stderr
        print(
            f"Successfully consolidated {len(files_processed)} Python files:",
            file=sys.stderr,
        )
        for f in sorted(files_processed):
            print(f"  - {f}", file=sys.stderr)

    else:
        print("No Python files found matching the include patterns.", file=sys.stderr)
