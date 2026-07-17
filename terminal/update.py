import os
import sys
import shutil
import zipfile
import re
import datetime
from pathlib import Path

# Try to import required packages, prompt user with instructions if missing
try:
    import requests
    import yaml
    import questionary
    from rich.console import Console
    from rich.panel import Panel
except ImportError:
    print("Error: Missing required packages.")
    print("Please activate your virtual environment (venv) or install dependencies manually:")
    print("  pip install requests PyYAML questionary rich")
    sys.exit(1)

console = Console()

# GitHub Repository Info
REPO_OWNER = "greenollie"
REPO_NAME = "OpenDoor"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

# Resolve project root directory
SCRIPT_DIR = Path(__file__).resolve().parent
if SCRIPT_DIR.name in ("test", "terminal"):
    PROJECT_ROOT = SCRIPT_DIR.parent
else:
    PROJECT_ROOT = SCRIPT_DIR

BACKUP_DIR = PROJECT_ROOT / "backup"
TEMP_DIR = PROJECT_ROOT / "temp_update"
TEMP_ZIP = PROJECT_ROOT / "update.zip"

def get_timestamp():
    """Generates timestamp in the format dd.mm.yyyy-hh.mm"""
    return datetime.datetime.now().strftime("%d.%m.%Y-%H.%M")

def copy_directory_excluding(src_dir, dest_dir, excludes):
    """Recursively copies files from src_dir to dest_dir, avoiding excluded items."""
    os.makedirs(dest_dir, exist_ok=True)
    for root, dirs, files in os.walk(src_dir):
        # Exclude directories in-place to prevent os.walk from entering them
        dirs[:] = [d for d in dirs if d not in excludes]
        
        rel_path = os.path.relpath(root, src_dir)
        target_root = dest_dir if rel_path == '.' else os.path.join(dest_dir, rel_path)
        os.makedirs(target_root, exist_ok=True)
        
        for file in files:
            if file in excludes:
                continue
            src_file = os.path.join(root, file)
            dest_file = os.path.join(target_root, file)
            try:
                shutil.copy2(src_file, dest_file)
            except Exception as e:
                console.print(f"    [bold #f38ba8]! Failed to backup file {file}: {e}[/bold #f38ba8]")

def create_backup():
    """Creates a backup of the root directory excluding large and transient paths."""
    timestamp = get_timestamp()
    backup_name = f"backup-{timestamp}"
    target_backup_path = BACKUP_DIR / backup_name
    
    console.print(f"\n[bold #89b4fa]Step 1/5: Creating backup in backup/{backup_name}...[/bold #89b4fa]")
    
    # Define files/directories to exclude from backup to save space and avoid recursive backup loops
    excludes = {
        "backup",
        "venv",
        ".venv",
        ".git",
        ".github",
        "__pycache__",
        "node_modules",
        "temp_update",
        "update.zip"
    }
    
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        os.makedirs(target_backup_path, exist_ok=True)
        
        copied_count = 0
        for item in os.listdir(PROJECT_ROOT):
            if item in excludes:
                continue
                
            src_path = PROJECT_ROOT / item
            dest_path = target_backup_path / item
            
            if src_path.is_dir():
                copy_directory_excluding(src_path, dest_path, excludes)
            else:
                shutil.copy2(src_path, dest_path)
                copied_count += 1
                
        console.print(f"[bold #a6e3a1]✓ Backup completed successfully in {target_backup_path}[/bold #a6e3a1]")
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Backup failed: {e}[/bold #f38ba8]")
        # Ask if user wants to proceed without backup
        proceed = questionary.confirm("Backup failed. Do you want to proceed with the update anyway?", default=False).ask()
        if not proceed:
            console.print("[bold #f38ba8]Update aborted by user.[/bold #f38ba8]")
            sys.exit(1)

def fetch_releases():
    """Queries GitHub Releases API to retrieve repository updates."""
    url = f"{GITHUB_API_URL}/releases"
    headers = {"User-Agent": "OpenDoor-Updater"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[bold #f38ba8]✗ GitHub API returned status code {response.status_code}[/bold #f38ba8]")
            return None
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Network connection to GitHub failed: {e}[/bold #f38ba8]")
        return None

def select_release(choice):
    """Filters fetched releases based on stable or pre-release choice."""
    releases = fetch_releases()
    if not releases:
        return None
        
    if choice == "stable":
        stable = [r for r in releases if not r.get("prerelease", False) and not r.get("draft", False)]
        if stable:
            return stable[0]
        else:
            console.print("[bold #f9e2af]No stable releases found. Checking latest pre-release updates...[/bold #f9e2af]")
            return releases[0] if releases else None
    else:
        # Includes pre-releases
        active = [r for r in releases if not r.get("draft", False)]
        return active[0] if active else None

def download_update(zipball_url):
    """Downloads the release zipball from GitHub."""
    console.print(f"\n[bold #89b4fa]Step 2/5: Downloading update package...[/bold #89b4fa]")
    headers = {"User-Agent": "OpenDoor-Updater"}
    try:
        if TEMP_ZIP.exists():
            os.remove(TEMP_ZIP)
            
        with requests.get(zipball_url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(TEMP_ZIP, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
        console.print("[bold #a6e3a1]✓ Download complete.[/bold #a6e3a1]")
        return True
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Download failed: {e}[/bold #f38ba8]")
        return False

def extract_update():
    """Extracts downloaded ZIP file to a temporary location."""
    console.print(f"[bold #89b4fa]Step 3/5: Extracting update files...[/bold #89b4fa]")
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        with zipfile.ZipFile(TEMP_ZIP, 'r') as zip_ref:
            zip_ref.extractall(TEMP_DIR)
            
        # GitHub zip archives wrap files in a single subfolder
        contents = os.listdir(TEMP_DIR)
        if len(contents) == 1 and (TEMP_DIR / contents[0]).is_dir():
            extracted_root = TEMP_DIR / contents[0]
            console.print("[bold #a6e3a1]✓ Extraction complete.[/bold #a6e3a1]")
            return extracted_root
        else:
            console.print("[bold #f38ba8]✗ Unexpected ZIP content structure.[/bold #f38ba8]")
            return None
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Extraction failed: {e}[/bold #f38ba8]")
        return None

def process_deletions(extracted_root):
    """Deletes files and directories matching lines specified in .updateconfig."""
    update_config_path = extracted_root / ".updateconfig"
    if not update_config_path.exists():
        return
        
    console.print(f"\n[bold #f9e2af]Step 4/5: Running post-update deletions (.updateconfig)...[/bold #f9e2af]")
    try:
        with open(update_config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            if line.startswith("del "):
                target_rel_path = line[4:].strip()
                if not target_rel_path:
                    continue
                
                # Standardize slashes and strip leading/trailing separators
                target_rel_path = target_rel_path.replace("\\", "/").strip("/")
                if not target_rel_path or target_rel_path in (".", ".."):
                    continue
                    
                local_target_path = PROJECT_ROOT / target_rel_path
                if local_target_path.exists():
                    try:
                        if local_target_path.is_dir():
                            shutil.rmtree(local_target_path)
                            console.print(f"  → Deleted directory: [bold #f38ba8]{target_rel_path}[/bold #f38ba8]")
                        else:
                            os.remove(local_target_path)
                            console.print(f"  → Deleted file: [bold #f38ba8]{target_rel_path}[/bold #f38ba8]")
                    except Exception as e:
                        console.print(f"  [bold #f38ba8]! Failed to delete {target_rel_path}: {e}[/bold #f38ba8]")
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Error processing deletions: {e}[/bold #f38ba8]")

def merge_yaml_config(template_path, user_path, output_path):
    """Merges user settings into the new template file, keeping formatting and comments."""
    user_values = {}
    if os.path.exists(user_path):
        try:
            with open(user_path, 'r', encoding='utf-8') as f:
                user_values = yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"    [bold #f9e2af]! Unable to load user configuration: {e}[/bold #f9e2af]")

    if not user_values:
        # Fallback to simple copy if there are no user values to merge
        shutil.copy2(template_path, output_path)
        return

    with open(template_path, 'r', encoding='utf-8') as f:
        template_lines = f.readlines()

    merged_lines = []
    i = 0
    num_lines = len(template_lines)

    while i < num_lines:
        line = template_lines[i]
        
        # Match "KEY:" at column 0 (YAML top-level parameters)
        match = re.match(r'^([A-Za-z0-9_-]+)\s*:\s*(.*)$', line)
        if match and not line.startswith('#'):
            key = match.group(1)
            
            # Find the complete block for this top-level key
            block_lines = [line]
            j = i + 1
            while j < num_lines:
                next_line = template_lines[j]
                next_stripped = next_line.strip()
                if not next_stripped:
                    block_lines.append(next_line)
                    j += 1
                elif next_line.startswith(' ') or next_line.startswith('\t'):
                    block_lines.append(next_line)
                    j += 1
                else:
                    break
            i = j
            
            # If the user has custom values for this parameter (and it isn't VERSION), override
            if key in user_values and key != "VERSION":
                user_val = user_values[key]
                
                # Check for inline comment on original key line
                comment = ""
                if "#" in line:
                    comment = "  #" + line.split("#", 1)[1].rstrip()
                
                # Convert user value to YAML format
                if isinstance(user_val, (list, dict)):
                    user_val_yaml = yaml.safe_dump(user_val, default_flow_style=False, sort_keys=False, allow_unicode=True).strip()
                    # Strip any trailing YAML document markers if present
                    if user_val_yaml.endswith('\n...'):
                        user_val_yaml = user_val_yaml[:-4]
                    elif user_val_yaml.endswith('...'):
                        user_val_yaml = user_val_yaml[:-3]
                    user_val_yaml = user_val_yaml.strip()
                else:
                    if isinstance(user_val, bool):
                        user_val_yaml = str(user_val).lower()
                    elif isinstance(user_val, (int, float)):
                        user_val_yaml = str(user_val)
                    elif user_val is None:
                        user_val_yaml = "null"
                    else:
                        escaped = str(user_val).replace('\\', '\\\\').replace('"', '\\"')
                        user_val_yaml = f'"{escaped}"'
                
                is_collection = isinstance(user_val, (list, dict))
                is_empty_collection = is_collection and not user_val
                
                if '\n' in user_val_yaml or (is_collection and not is_empty_collection):
                    # Multiline indentation
                    indented = [f"  {vl}\n" for vl in user_val_yaml.splitlines()]
                    merged_lines.append(f"{key}:{comment}\n")
                    merged_lines.extend(indented)
                else:
                    # Flat single-line format
                    merged_lines.append(f"{key}: {user_val_yaml}{comment}\n")
            else:
                # Keep original example setting block
                merged_lines.extend(block_lines)
        else:
            # Add comments and spacing lines unmodified
            merged_lines.append(line)
            i += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(merged_lines)

def update_files(extracted_root):
    """Copies new and modified files from extracted source to destination, merging YAML templates."""
    console.print(f"\n[bold #89b4fa]Step 5/5: Merging and updating files...[/bold #89b4fa]")
    
    # Identify which optional subprograms currently exist locally
    local_sub_programs_dir = PROJECT_ROOT / "sub-programs"
    existing_sub_programs = set()
    if local_sub_programs_dir.exists() and local_sub_programs_dir.is_dir():
        for item in os.listdir(local_sub_programs_dir):
            if (local_sub_programs_dir / item).is_dir():
                existing_sub_programs.add(item)
                
    for root, dirs, files in os.walk(extracted_root):
        rel_path = os.path.relpath(root, extracted_root)
        
        # Filter sub-programs copy logic
        path_parts = Path(rel_path).parts
        if len(path_parts) >= 2 and path_parts[0] == "sub-programs":
            sub_prog_name = path_parts[1]
            if sub_prog_name not in existing_sub_programs:
                dirs[:] = []  # Do not walk subdirectories of non-existent subprograms
                continue
        elif len(path_parts) == 1 and path_parts[0] == "sub-programs":
            # Walk only the sub-programs directories that exist locally
            dirs[:] = [d for d in dirs if d in existing_sub_programs]
            
        target_dir = PROJECT_ROOT if rel_path == '.' else PROJECT_ROOT / rel_path
        os.makedirs(target_dir, exist_ok=True)
        
        for file in files:
            # Skip updating configuration templates globally (we process them explicitly)
            if file == ".updateconfig":
                continue
                
            src_file = Path(root) / file
            dest_file = target_dir / file
            
            # YAML template merging logic
            if file.endswith(".yaml.example"):
                yaml_name = file[:-8]  # Strip ".example" suffix
                dest_yaml_file = target_dir / yaml_name
                
                # Copy example template file
                shutil.copy2(src_file, dest_file)
                console.print(f"  → Updated template: {dest_file.relative_to(PROJECT_ROOT)}", style="#585b70")
                
                # Perform YAML merge
                if dest_yaml_file.exists():
                    console.print(f"  → Merging settings: {yaml_name} in {rel_path if rel_path != '.' else 'root'}", style="#cdd6f4")
                    try:
                        merge_yaml_config(src_file, dest_yaml_file, dest_yaml_file)
                    except Exception as e:
                        console.print(f"    [bold #f38ba8]! Failed to merge config {yaml_name}: {e}. Overwriting with default template.[/bold #f38ba8]")
                        shutil.copy2(src_file, dest_yaml_file)
                else:
                    console.print(f"  → Created config: {yaml_name}", style="#a6e3a1")
                    shutil.copy2(src_file, dest_yaml_file)
            else:
                # Standard file copying
                is_replacement = dest_file.exists()
                action_text = "Replaced" if is_replacement else "Added"
                
                try:
                    shutil.copy2(src_file, dest_file)
                    console.print(f"  → {action_text}: {dest_file.relative_to(PROJECT_ROOT)}", style="#a6adc8")
                except Exception as e:
                    console.print(f"    [bold #f38ba8]! Failed to copy {file}: {e}[/bold #f38ba8]")
                    
    return existing_sub_programs

def download_github_folder(repo_path, local_dir, ref=None):
    """Recursively downloads directory contents from GitHub repository at a specific tag/ref."""
    local_dir = Path(local_dir)
    api_url = f"https://api.github.com/repos/greenollie/OpenDoor/contents/{repo_path}"
    if ref:
        api_url += f"?ref={ref}"
        
    headers = {
        "User-Agent": "OpenDoor-Updater"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        if response.status_code != 200:
            console.print(f"  [bold #f38ba8]✗ Failed to access GitHub API for '{repo_path}'. (HTTP Status: {response.status_code})[/bold #f38ba8]")
            return
            
        items = response.json()
    except Exception as e:
        console.print(f"  [bold #f38ba8]✗ Failed to download/parse JSON from GitHub for '{repo_path}': {e}[/bold #f38ba8]")
        return
        
    if not isinstance(items, list):
        return
        
    os.makedirs(local_dir, exist_ok=True)
    
    for item in items:
        name = item.get('name')
        item_type = item.get('type')
        
        if item_type == 'file':
            file_url = item.get('download_url')
            local_file_path = local_dir / name
            is_yaml_example = name.endswith(".yaml.example")
            
            console.print(f"    → Downloading: {repo_path}/{name}", style="#585b70")
            try:
                file_data = requests.get(file_url, headers=headers, timeout=30).content
                
                if is_yaml_example:
                    # Save template
                    with open(local_file_path, 'wb') as f:
                        f.write(file_data)
                        
                    yaml_name = name[:-8]  # Strip ".example" suffix
                    dest_yaml_file = local_dir / yaml_name
                    if dest_yaml_file.exists():
                        console.print(f"      → Merging config: {yaml_name}", style="#cdd6f4")
                        merge_yaml_config(local_file_path, dest_yaml_file, dest_yaml_file)
                    else:
                        console.print(f"      → Created config: {yaml_name}", style="#a6e3a1")
                        shutil.copy2(local_file_path, dest_yaml_file)
                else:
                    # Normal file write
                    with open(local_file_path, 'wb') as f:
                        f.write(file_data)
            except Exception as e:
                console.print(f"    [bold #f38ba8]✗ Failed to write/merge file {name}: {e}[/bold #f38ba8]")
                
        elif item_type == 'dir':
            subfolder_name = item.get('name')
            new_repo_path = f"{repo_path}/{subfolder_name}"
            new_local_dir = local_dir / subfolder_name
            download_github_folder(new_repo_path, new_local_dir, ref)

def update_subprograms(existing_sub_programs, tag_name):
    """Downloads updated files for active subprograms directly from the selected release tag."""
    if not existing_sub_programs:
        return
        
    console.print(f"\n[bold #89b4fa]Step 5.5: Syncing active subprograms ({', '.join(existing_sub_programs)}) from release {tag_name}...[/bold #89b4fa]")
    
    for sub_name in existing_sub_programs:
        console.print(f"[bold #f9e2af]Syncing sub-program: {sub_name}...[/bold #f9e2af]")
        repo_path = f"sub-programs/{sub_name}"
        local_dir = PROJECT_ROOT / "sub-programs" / sub_name
        
        # Download and merge files for the specific tag
        download_github_folder(repo_path, local_dir, ref=tag_name)
        console.print(f"[bold #a6e3a1]✓ {sub_name} updated successfully.[/bold #a6e3a1]")

def cleanup():
    """Removes temporary update assets and destination config remnants."""
    console.print(f"\n[bold #89b4fa]Cleaning up temporary files...[/bold #89b4fa]")
    
    # Remove ZIP package
    if TEMP_ZIP.exists():
        try:
            os.remove(TEMP_ZIP)
        except Exception:
            pass
            
    # Remove extracted temporary directory
    if TEMP_DIR.exists():
        try:
            shutil.rmtree(TEMP_DIR)
        except Exception:
            pass
            
    # Delete the active `.updateconfig` file in project root if it exists
    local_updateconfig = PROJECT_ROOT / ".updateconfig"
    if local_updateconfig.exists():
        try:
            os.remove(local_updateconfig)
            console.print("✓ Deleted .updateconfig in destination folder.")
        except Exception as e:
            console.print(f"[bold #f9e2af]! Failed to delete .updateconfig: {e}[/bold #f9e2af]")
            
    console.print("[bold #a6e3a1]✓ Cleanup complete.[/bold #a6e3a1]")

def main():
    console.print(Panel("[bold #89b4fa]OpenDoor Updater[/bold #89b4fa]\nAuto-updating without breaking configurations or deleting custom data.", border_style="#89b4fa"))
    
    # 1. Ask user for update channel
    choice = questionary.select(
        "Choose an update channel:",
        choices=[
            {"name": "Latest Release (Stable)", "value": "stable"},
            {"name": "Latest Update (Includes Pre-releases)", "value": "pre-release"},
            {"name": "Cancel", "value": "cancel"}
        ]
    ).ask()
    
    if choice == "cancel" or not choice:
        console.print("[bold #f38ba8]Update cancelled.[/bold #f38ba8]")
        return
        
    # 2. Select version from GitHub API
    console.print("[bold #89b4fa]Checking for updates on GitHub...[/bold #89b4fa]")
    release = select_release(choice)
    if not release:
        console.print("[bold #f38ba8]No suitable update found. Please check your internet connection and try again.[/bold #f38ba8]")
        return
        
    tag_name = release.get("tag_name", "Unknown Version")
    body = release.get("body", "No release description provided.")
    publish_date = release.get("published_at", "Unknown Date")
    zipball_url = release.get("zipball_url")
    
    console.print(f"\n[bold #cdd6f4]Found update: [bold #89b4fa]{tag_name}[/bold #89b4fa] (Published: {publish_date})[/bold #cdd6f4]")
    
    # Display formatted release description excerpt
    truncated_body = body[:500] + "..." if len(body) > 500 else body
    console.print(Panel(truncated_body, title="Release Notes excerpt", border_style="#585b70"))
    
    # 3. Confirm with user
    confirm = questionary.confirm(f"Do you want to download and apply {tag_name}?", default=True).ask()
    if not confirm:
        console.print("[bold #f38ba8]Update cancelled.[/bold #f38ba8]")
        return
        
    if not zipball_url:
        console.print("[bold #f38ba8]✗ Release payload doesn't contain a zipball URL. Aborting update.[/bold #f38ba8]")
        return
        
    # 4. Perform update sequence
    create_backup()
    
    if download_update(zipball_url):
        extracted_root = extract_update()
        if extracted_root:
            process_deletions(extracted_root)
            existing_sub_programs = update_files(extracted_root)
            update_subprograms(existing_sub_programs, tag_name)
            cleanup()
            console.print(f"\n[bold #a6e3a1]★ OpenDoor successfully updated to {tag_name}! ★[/bold #a6e3a1]")
        else:
            cleanup()
    else:
        cleanup()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold #f38ba8]Update interrupted by user.[/bold #f38ba8]")
        cleanup()
