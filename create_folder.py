import os
import shutil
import argparse

# --- Configuration ---

# Define supported extensions (non-Advanced based on your list) - lowercase
# Excludes: XLS, XLSX, CSV, TSV (marked as Advanced only)
SUPPORTED_EXTENSIONS = {
    # Code
    'c', 'cpp', 'py', 'java', 'php', 'sql', 'html',
    # Document
    'doc', 'docx', 'pdf', 'rtf', 'dot', 'dotx', 'hwp', 'hwpx',
    # Plain text
    'txt',
    # Presentation
    'pptx',
    # Note: Google Docs/Sheets/Slides are web formats, not typically local files
    # in a way this script processes. Users would export them first.
}

# Define extensions to ignore completely (common multimedia, archives, etc.) - lowercase
IGNORED_EXTENSIONS = {
    # Images
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'svg', 'webp', 'ico',
    # Audio
    'mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a',
    # Video
    'mp4', 'mov', 'avi', 'mkv', 'webm', 'wmv', 'flv',
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz',
    # Executables/System
    'exe', 'dll', 'so', 'dylib', 'dmg', 'app', 'iso', 'bin', 'msi', 'jar',
    # Fonts
    'ttf', 'otf', 'woff', 'woff2',
    # Other common non-text/non-code
    'psd', 'ai', 'eps', 'indd', 'obj', 'stl', 'pdb', 'log', # Added .log as often large/verbose
    # Common config / env files that might be sensitive or large
     'env', 'lock',
    # IDE/Build tool specific folders/files (often contain generated/binary)
    'o', 'a', 'lib', 'class', 'pyc', 'pyd', # Common build artifacts
    # Add more extensions here if needed
}

# Size limit for warning
MAX_SIZE_MB = 100
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

# --- Helper Functions ---

def get_safe_filename(name):
    """Removes potentially problematic characters for filenames, though '%' is kept for hierarchy."""
    # Basic sanitization - you might want to expand this if needed
    # For now, primarily ensures it doesn't contain path separators by mistake after replacements
    return name.replace('/', '_').replace('\\', '_')

# --- Core Logic ---

def prepare_gemini_upload(input_dir, output_dir):
    """
    Prepares a folder for uploading to Gemini's code feature by flattening the
    structure, converting unsupported text-like files to .txt, and ignoring
    multimedia/binary files.

    Args:
        input_dir (str): Path to the source directory.
        output_dir (str): Path to the destination directory to be created.
    """
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' not found or is not a directory.")
        return

    # Resolve paths to absolute to prevent issues with relative paths
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir)

    # Prevent processing the output directory if it's inside the input directory
    if output_dir.startswith(input_dir) and output_dir != input_dir:
         print(f"Error: Output directory '{output_dir}' cannot be inside the input directory '{input_dir}'.")
         return

    if os.path.exists(output_dir):
        if not os.path.isdir(output_dir):
            print(f"Error: Output path '{output_dir}' exists but is not a directory.")
            return
        elif os.listdir(output_dir):
            print(f"Warning: Output directory '{output_dir}' exists and is not empty. Files might be overwritten.")
    else:
        try:
            os.makedirs(output_dir)
            print(f"Created output directory: '{output_dir}'")
        except OSError as e:
            print(f"Error: Could not create output directory '{output_dir}': {e}")
            return

    print(f"\nProcessing files from '{input_dir}' into '{output_dir}'...")

    total_size = 0
    processed_files = 0
    ignored_files = 0
    converted_files = 0
    error_files = 0

    # Common directories to skip
    skip_dirs = {'.git', '.svn', '.vscode', '.idea', 'node_modules', '__pycache__', 'venv', '.env'}

    for root, dirs, files in os.walk(input_dir, topdown=True):
        # Modify dirs in-place to prevent descending into skipped/hidden directories
        # This is the primary mechanism for skipping whole directories
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

        # Skip processing the output directory itself if os.walk picks it up
        if os.path.abspath(root).startswith(output_dir):
             continue

        relative_dir_path = os.path.relpath(root, input_dir)

        for filename in files:
            # Skip hidden files (e.g., .gitignore, .env)
            if filename.startswith('.'):
                ignored_files += 1
                continue

            source_path = os.path.join(root, filename)
            base_name, ext = os.path.splitext(filename)
            file_ext_lower = ext[1:].lower() if ext else ''

            # --- 1. Check if extension is explicitly ignored ---
            #    (The check for ignored *directories* is handled by dirs[:] above)
            if file_ext_lower in IGNORED_EXTENSIONS:
                ignored_files += 1
                # print(f"Ignoring: {source_path} (Ignored Extension: {file_ext_lower})")
                continue
            # --- V V V FAULTY CHECK REMOVED HERE V V V ---
            # is_ignored_dir = any(part in skip_dirs or part.startswith('.') for part in relative_dir_path.split(os.sep))
            # if file_ext_lower in IGNORED_EXTENSIONS or is_ignored_dir: # <--- This line was the problem
            #     ignored_files += 1
            #     continue
            # --- ^ ^ ^ FAULTY CHECK REMOVED HERE ^ ^ ^ ---


            # --- 2. Construct new filename base based on relative path ---
            if relative_dir_path == '.':
                # File is in the root input directory
                new_filename_base = filename
            else:
                # File is in a subdirectory
                prefix = relative_dir_path.replace(os.sep, '%')
                safe_prefix = get_safe_filename(prefix)
                new_filename_base = f"{safe_prefix}%{filename}"

            # --- 3. Check if supported extension ---
            if file_ext_lower in SUPPORTED_EXTENSIONS:
                target_path = os.path.join(output_dir, new_filename_base)
                try:
                    shutil.copy2(source_path, target_path) # copy2 preserves metadata
                    total_size += os.path.getsize(target_path)
                    processed_files += 1
                    # print(f"Copied: {filename} -> {new_filename_base}")
                except Exception as e:
                    print(f"Error copying {source_path} to {target_path}: {e}")
                    error_files += 1

            # --- 4. If not ignored and not supported, attempt to convert to .txt ---
            else:
                target_filename = f"{new_filename_base}.txt"
                target_path = os.path.join(output_dir, target_filename)
                try:
                    # Try reading as UTF-8, replacing errors
                    with open(source_path, 'r', encoding='utf-8', errors='replace') as infile:
                        content = infile.read()

                    # Write the content to the new .txt file
                    with open(target_path, 'w', encoding='utf-8') as outfile:
                        outfile.write(content)

                    total_size += os.path.getsize(target_path)
                    processed_files += 1
                    converted_files += 1
                    # print(f"Converted: {filename} -> {target_filename}")

                except UnicodeDecodeError:
                    # File is likely binary
                    try:
                         with open(target_path, 'w', encoding='utf-8') as outfile:
                             outfile.write(f"[Content of '{filename}' could not be decoded as text (likely binary). Original extension: {ext}]")
                         total_size += os.path.getsize(target_path)
                         processed_files += 1
                         converted_files += 1
                         # print(f"Placeholder created for undecodable file: {filename} -> {target_filename}")
                    except Exception as e:
                        print(f"Error creating placeholder for {source_path} at {target_path}: {e}")
                        error_files += 1
                except MemoryError:
                     print(f"Error: MemoryError while trying to read {source_path}. File might be too large to process this way.")
                     error_files += 1
                     try:
                          with open(target_path, 'w', encoding='utf-8') as outfile:
                              outfile.write(f"[Content of '{filename}' could not be read due to MemoryError (file too large?). Original extension: {ext}]")
                          total_size += os.path.getsize(target_path) # Size of placeholder
                          processed_files += 1
                          converted_files += 1
                     except Exception as e_mem:
                         print(f"Error creating placeholder after MemoryError for {source_path}: {e_mem}")

                except Exception as e:
                    print(f"Error processing/converting {source_path} to {target_path}: {e}")
                    error_files += 1

    # --- Final Summary & Warning ---
    # (This part remains the same)
    print("\n--- Processing Summary ---")
    print(f"Files processed (copied or converted): {processed_files}")
    print(f"Files converted to .txt: {converted_files}")
    print(f"Files/Directories ignored or skipped: {ignored_files}")
    if error_files > 0:
         print(f"Errors encountered: {error_files}")

    final_size_mb = total_size / (1024 * 1024)
    print(f"Final size of output folder '{output_dir}': {final_size_mb:.2f} MB")

    if total_size > MAX_SIZE_BYTES:
        print("\n--------------------------------------------------------------------")
        print(f"WARNING: Output folder size ({final_size_mb:.2f} MB) exceeds the recommended {MAX_SIZE_MB} MB limit.")
        print("         Gemini might struggle or fail to process folders this large.")
        print("         Consider reducing the input scope or removing large files.")
        print("--------------------------------------------------------------------")
    elif final_size_mb > 0:
         print(f"\nOutput folder size is within the recommended {MAX_SIZE_MB} MB limit.")

    print("\nScript finished.")

# --- Command Line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare a folder for Gemini code upload. Flattens structure, converts unsupported text-like files to .txt, ignores multimedia/binary.",
        formatter_class=argparse.RawTextHelpFormatter # Allows newlines in help text
        )
    parser.add_argument("input_dir",
                        help="Path to the source directory containing your project files.")
    parser.add_argument("output_dir",
                        help="Path to the destination directory where the processed files will be saved.\nThis directory will be created if it doesn't exist.")

    print("Gemini File Prep Tool")
    print("---------------------\n")
    print("Supported extensions (will be copied):")
    print(f"  {', '.join(sorted(list(SUPPORTED_EXTENSIONS)))}\n")
    print("Ignored extensions (will be skipped):")
    print(f"  {', '.join(sorted(list(IGNORED_EXTENSIONS)))}\n")
    print("Other file types will be converted to .txt (if text-readable).\n")


    args = parser.parse_args()

    prepare_gemini_upload(args.input_dir, args.output_dir)