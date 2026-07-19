import os
import sys
import time
import shutil
import subprocess
import requests
import yaml
import questionary
import pyfiglet
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from questionary import Style

console = Console()

# Catppuccin Mocha colors matching the TUI theme
tui_style = Style([
    ('qmark', 'fg:#89B4FA bold'),       # pink
    ('question', 'bold fg:#cdd6f4'),    # text
    ('answer', 'fg:#89b4fa bold'),      # blue
    ('pointer', 'fg:#89B4FA bold'),     # pink
    ('highlighted', 'fg:#89B4FA bold'), # pink
    ('selected', 'fg:#89dceb'),         # sky
    ('separator', 'fg:#45475a'),        # surface1
    ('instruction', 'fg:#a6adc8'),      # subtext0
    ('text', 'fg:#cdd6f4'),             # text
    ('disabled', 'fg:#313244'),         # surface0
])

def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

# Resolve directories
SCRIPT_DIR = Path(__file__).resolve().parent
if SCRIPT_DIR.name in ("test", "terminal"):
    PROJECT_ROOT = SCRIPT_DIR.parent
else:
    PROJECT_ROOT = SCRIPT_DIR

CONFIG_FILE = PROJECT_ROOT / "config.yaml"
EXAMPLE_FILE = PROJECT_ROOT / "config.yaml.example"

def get_current_version():
    version = None
    for file_path in (CONFIG_FILE, EXAMPLE_FILE):
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    version = cfg.get("VERSION")
                    if version:
                        break
            except Exception:
                pass
    return version

def download_github_folder(repo_path, local_dir, ref=None):
    local_dir = Path(local_dir)
    api_url = f"https://api.github.com/repos/greenollie/OpenDoor/contents/{repo_path}"
    if ref:
        api_url += f"?ref={ref}"
    
    headers = {
        "User-Agent": "OpenDoor-Setup-Wizard"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Network connection to GitHub failed: {e}[/bold #f38ba8]")
        return False
    
    if response.status_code != 200:
        if response.status_code == 404 and ref:
            sub_program = repo_path.split('/')[-1]
            console.print(f"[bold #f38ba8]✗ A complimentary version '{ref}' of the sub-program '{sub_program}' could not be found.[/bold #f38ba8]")
            
            # Fetch tags and branches
            choices = []
            
            # Fetch branches
            try:
                branches_url = "https://api.github.com/repos/greenollie/OpenDoor/branches"
                br_resp = requests.get(branches_url, headers=headers, timeout=10)
                if br_resp.status_code == 200:
                    choices.extend([b['name'] for b in br_resp.json() if 'name' in b])
            except Exception:
                pass
                
            # Fetch tags
            try:
                tags_url = "https://api.github.com/repos/greenollie/OpenDoor/tags"
                t_resp = requests.get(tags_url, headers=headers, timeout=10)
                if t_resp.status_code == 200:
                    choices.extend([t['name'] for t in t_resp.json() if 'name' in t])
            except Exception:
                pass
            
            # De-duplicate and ensure main/master are included
            unique_choices = []
            for c in choices:
                if c not in unique_choices:
                    unique_choices.append(c)
            
            if "main" not in unique_choices:
                unique_choices.insert(0, "main")
            if "master" not in unique_choices and "master" in choices:
                unique_choices.append("master")
                
            unique_choices.append("Enter version/ref manually...")
            
            selected_ref = ask_with_tick(
                questionary.select(
                    "Please select an alternative version to download:",
                    choices=unique_choices,
                    style=tui_style
                ),
                "Please select an alternative version to download:"
            )
            
            if selected_ref == "Enter version/ref manually...":
                selected_ref = ask_with_tick(
                    questionary.text(
                        "Enter custom version/ref (branch, tag, or commit SHA):",
                        style=tui_style
                    ),
                    "Enter custom version/ref (branch, tag, or commit SHA):"
                )
            
            if not selected_ref:
                return False
                
            console.print(f"[bold #f9e2af]Retrying download of sub-program: {sub_program} (version {selected_ref})...[/bold #f9e2af]")
            return download_github_folder(repo_path, local_dir, ref=selected_ref)
        else:
            console.print(f"[bold #f38ba8]✗ Failed to access GitHub API for path '{repo_path}'. (HTTP Status: {response.status_code})[/bold #f38ba8]")
            return False

    try:
        items = response.json()
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Failed to parse JSON response: {e}[/bold #f38ba8]")
        return False
    
    # Create the local directory if it doesn't exist
    os.makedirs(local_dir, exist_ok=True)
    
    success = True
    for item in items:
        if item['type'] == 'file':
            file_name = item['name']
            file_url = item['download_url']
            local_file_path = local_dir / file_name
            
            console.print(f"  → Downloading: {repo_path}/{file_name}", style="#585b70")
            try:
                file_data = requests.get(file_url, headers=headers, timeout=15).content
                with open(local_file_path, 'wb') as f:
                    f.write(file_data)
            except Exception as e:
                console.print(f"  [bold #f38ba8]✗ Failed to download {file_name}: {e}[/bold #f38ba8]")
                success = False
                
        elif item['type'] == 'dir':
            subfolder_name = item['name']
            new_repo_path = f"{repo_path}/{subfolder_name}"
            new_local_dir = local_dir / subfolder_name
            
            if not download_github_folder(new_repo_path, new_local_dir, ref):
                success = False
                
    return success

def update_line_config(lines, key, value):
    if key == "DISABLE_WEATHER" and value is False:
        # If the user has added their location, DISABLE_WEATHER should not be added to the config,
        # and if it already exists in the config, it should be removed.
        idx_to_remove = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("#") and ":" in stripped:
                k = stripped.split(":", 1)[0].strip()
                if k == "DISABLE_WEATHER":
                    idx_to_remove = i
                    break
        if idx_to_remove is not None:
            lines_to_del = [idx_to_remove]
            if idx_to_remove > 0:
                prev_line = lines[idx_to_remove - 1]
                if "# DISABLE_WEATHER:" in prev_line:
                    lines_to_del.append(idx_to_remove - 1)
                    if idx_to_remove > 1 and lines[idx_to_remove - 2].strip() == "":
                        lines_to_del.append(idx_to_remove - 2)
            for idx in sorted(lines_to_del, reverse=True):
                lines.pop(idx)
        return

    found = False
    new_value_str = f"\"{value}\"" if isinstance(value, str) else str(value).lower() if isinstance(value, bool) else str(value)
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#") and ":" in stripped:
            k = stripped.split(":", 1)[0].strip()
            if k == key:
                parts = line.split("#", 1)
                comment_part = f" # {parts[1].strip()}" if len(parts) > 1 else ""
                indent = line[:len(line) - len(line.lstrip())]
                lines[i] = f"{indent}{key}: {new_value_str}{comment_part}"
                found = True
                break
                
    if not found:
        if key == "DISABLE_WEATHER":
            lines.append("")
            lines.append("# DISABLE_WEATHER: Toggle weather tool visibility/execution.")
        elif key == "OPENAI_API_KEY":
            lines.append("")
            lines.append("# OPENAI_API_KEY: The API key for accessing OpenAI services.")
        lines.append(f"{key}: {new_value_str}")

def update_config(latitude, longitude, default_model, subagent_model, disable_weather):
    base_file = CONFIG_FILE if CONFIG_FILE.exists() else EXAMPLE_FILE
    
    if not base_file.exists():
        console.print(f"[bold #f38ba8]✗ Error: Neither config.yaml nor config.yaml.example was found in {PROJECT_ROOT}[/bold #f38ba8]")
        return
        
    try:
        with open(base_file, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Error reading template file: {e}[/bold #f38ba8]")
        return

    update_line_config(lines, "LATITUDE", float(latitude))
    update_line_config(lines, "LONGITUDE", float(longitude))
    update_line_config(lines, "DEFAULT_MODEL", default_model)
    update_line_config(lines, "SUBAGENT_MODEL", subagent_model)
    update_line_config(lines, "DISABLE_WEATHER", disable_weather)

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Error writing configuration file: {e}[/bold #f38ba8]")

def ask_with_tick(question_obj, message, answer_formatter=None):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    answer = question_obj.unsafe_ask()
    ans_display = answer_formatter(answer) if answer_formatter else str(answer)
    sys.stdout.write("\033[A\r\033[K")
    sys.stdout.flush()
    
    is_negative = False
    if isinstance(answer, bool):
        is_negative = not answer
    elif str(answer) in ("Cancel", "Exit", "None", "cancel", "exit"):
        is_negative = True

    if is_negative:
        console.print(f"[bold #f38ba8]✗[/bold #f38ba8] [bold #cdd6f4]{message}[/bold #cdd6f4] [#f38ba8]{ans_display}[/#f38ba8]")
    else:
        console.print(f"[bold #89B4FA]✓[/bold #89B4FA] [bold #cdd6f4]{message}[/bold #cdd6f4] [#89b4fa]{ans_display}[/#89b4fa]")
    return answer

def edit_main_config():
    # Load existing config values for defaults
    default_main = "gpt-5.4-nano"
    default_sub = "gpt-5.4-mini"
    current_lat = 0.0
    current_lon = 0.0
    current_disable_weather = False

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                default_main = cfg.get("DEFAULT_MODEL", default_main)
                default_sub = cfg.get("SUBAGENT_MODEL", default_sub)
                current_lat = cfg.get("LATITUDE", current_lat)
                current_lon = cfg.get("LONGITUDE", current_lon)
                current_disable_weather = cfg.get("DISABLE_WEATHER", current_disable_weather)
        except Exception:
            pass

    # 1. Main Model Selection
    MODEL_CHOICES = [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.5-pro",
        "gpt-5.5",
        "gpt-5.4-pro",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "Custom (Enter manually)"
    ]
    
    main_choices = MODEL_CHOICES.copy()
    if default_main not in main_choices:
        custom_index = main_choices.index("Custom (Enter manually)")
        main_choices.insert(custom_index, default_main)

    selected_main = ask_with_tick(
        questionary.select(
            "Select the main AI model:",
            choices=main_choices,
            style=tui_style
        ),
        "Select the main AI model:"
    )

    if selected_main == "Custom (Enter manually)":
        selected_main = ask_with_tick(
            questionary.text(
                "Enter the name of your custom main model:",
                style=tui_style
            ),
            "Enter the name of your custom main model:"
        )

    # 2. Subagent Model Selection
    sub_choices = MODEL_CHOICES.copy()
    if default_sub not in sub_choices:
        custom_index = sub_choices.index("Custom (Enter manually)")
        sub_choices.insert(custom_index, default_sub)

    selected_sub = ask_with_tick(
        questionary.select(
            "Select the subagent AI model:",
            choices=sub_choices,
            style=tui_style
        ),
        "Select the subagent AI model:"
    )

    if selected_sub == "Custom (Enter manually)":
        selected_sub = ask_with_tick(
            questionary.text(
                "Enter the name of your custom subagent model:",
                style=tui_style
            ),
            "Enter the name of your custom subagent model:"
        )

    # 3. Weather Location Setup
    location_option = ask_with_tick(
        questionary.select(
            "Configure weather tool location:",
            choices=[
                "Auto-detect location using IP address (Recommended)",
                "Enter coordinates manually (Latitude / Longitude)",
                "Disable weather tool"
            ],
            style=tui_style
        ),
        "Configure weather tool location:"
    )

    lat_val = current_lat
    lon_val = current_lon
    disable_weather_val = current_disable_weather

    if location_option.startswith("Auto-detect"):
        try:
            r = requests.get("http://ip-api.com/json", timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    lat_val = data.get("lat")
                    lon_val = data.get("lon")
                    city = data.get("city")
                    country = data.get("country")
                    console.print(f"[bold #89b4fa]✓[/bold #89b4fa] [bold #cdd6f4]Detected location:[/bold #cdd6f4] [bold #89b4fa]{city}, {country}[/bold #89b4fa] ([bold #89b4fa]{lat_val}, {lon_val}[/bold #89b4fa])")
                    disable_weather_val = False
                else:
                    console.print("[bold #f38ba8]✗ Failed to parse location from response. Falling back to manual input.[/bold #f38ba8]")
                    location_option = "Enter coordinates manually (Latitude / Longitude)"
            else:
                console.print(f"[bold #f38ba8]✗ Geolocation API returned status code {r.status_code}. Falling back to manual input.[/bold #f38ba8]")
                location_option = "Enter coordinates manually (Latitude / Longitude)"
        except Exception as e:
            console.print(f"[bold #f38ba8]✗ Geolocation request failed: {e}. Falling back to manual input.[/bold #f38ba8]")
            location_option = "Enter coordinates manually (Latitude / Longitude)"

    if location_option.startswith("Enter coordinates"):
        lat_input = ask_with_tick(
            questionary.text(
                "Enter Latitude:",
                validate=lambda val: True if is_float(val) and -90 <= float(val) <= 90 else "Please enter a valid latitude (-90 to 90)",
                style=tui_style
            ),
            "Enter Latitude:"
        )
        lon_input = ask_with_tick(
            questionary.text(
                "Enter Longitude:",
                validate=lambda val: True if is_float(val) and -180 <= float(val) <= 180 else "Please enter a valid longitude (-180 to 180)",
                style=tui_style
            ),
            "Enter Longitude:"
        )
        lat_val = float(lat_input)
        lon_val = float(lon_input)
        disable_weather_val = False

    elif location_option.startswith("Disable"):
        disable_weather_val = True
        lat_val = current_lat if current_lat else 0.0
        lon_val = current_lon if current_lon else 0.0

    # Save to config.yaml
    update_config(
        latitude=lat_val,
        longitude=lon_val,
        default_model=selected_main,
        subagent_model=selected_sub,
        disable_weather=disable_weather_val
    )
    console.print(f"[bold #a6e3a1]✓ Main configuration saved successfully to {CONFIG_FILE.name}[/bold #a6e3a1]\n")

def edit_whatsapp_config(config_path, example_path):
    if not config_path.exists():
        if example_path.exists():
            shutil.copy(example_path, config_path)
            console.print(f"[bold #89b4fa]✓[/bold #89b4fa] [bold #cdd6f4]Copied example WhatsApp config to {config_path.name}[/bold #cdd6f4]")
        else:
            console.print(f"[bold #f38ba8]✗ Error: WhatsApp example config not found at {example_path}[/bold #f38ba8]")
            return

    # Load existing config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Error reading WhatsApp config: {e}[/bold #f38ba8]")
        cfg = {}

    current_allowlist = cfg.get("ID_ALLOWLIST", ["123456789012345"])
    current_trigger_prefix = cfg.get("TRIGGER_PREFIX", "to ai:")
    current_you_chat_perms = cfg.get("ADDITIONAL_YOU_CHAT_PERMISSIONS", True)
    current_reply_prefix = cfg.get("REPLY_PREFIX", "{AI_NAME}:\n\n")
    current_self_chat_agent = cfg.get("SELF_CHAT_AGENT", "Terry")
    current_default_agent = cfg.get("DEFAULT_AGENT", "Terry")

    # 1. PHONE NUMBER ALLOWLIST
    default_allowlist_str = ", ".join(current_allowlist) if isinstance(current_allowlist, list) else str(current_allowlist)
    allowlist_input = ask_with_tick(
        questionary.text(
            "Enter authorized WhatsApp phone numbers/IDs (comma-separated):",
            default=default_allowlist_str,
            style=tui_style
        ),
        "Enter authorized WhatsApp phone numbers/IDs (comma-separated):"
    )
    new_allowlist = [x.strip() for x in allowlist_input.split(",") if x.strip()]

    # 2. TRIGGER PREFIX
    new_trigger_prefix = ask_with_tick(
        questionary.text(
            "Enter trigger prefix (e.g. 'to ai:', or leave empty for none):",
            default=current_trigger_prefix,
            style=tui_style
        ),
        "Enter trigger prefix:"
    )

    # 3. ADDITIONAL YOU CHAT PERMISSIONS
    new_you_chat_perms = ask_with_tick(
        questionary.confirm(
            "Enable replying to own messages in self-chats without prefix?",
            default=current_you_chat_perms,
            style=tui_style
        ),
        "Enable replying to own messages in self-chats without prefix?"
    )

    # 4. REPLY PREFIX
    default_reply_prefix_escaped = current_reply_prefix.replace("\n", "\\n")
    reply_prefix_input = ask_with_tick(
        questionary.text(
            "Enter reply prefix (use \\n for newlines):",
            default=default_reply_prefix_escaped,
            style=tui_style
        ),
        "Enter reply prefix:"
    )
    new_reply_prefix = reply_prefix_input.replace("\\n", "\n")

    # 5. SELF CHAT AGENT
    new_self_chat_agent = ask_with_tick(
        questionary.text(
            "Enter self-chat agent name:",
            default=current_self_chat_agent,
            style=tui_style
        ),
        "Enter self-chat agent name:"
    )

    # 6. DEFAULT AGENT
    new_default_agent = ask_with_tick(
        questionary.text(
            "Enter fallback/default agent name:",
            default=current_default_agent,
            style=tui_style
        ),
        "Enter fallback/default agent name:"
    )

    cfg["ID_ALLOWLIST"] = new_allowlist
    cfg["TRIGGER_PREFIX"] = new_trigger_prefix
    cfg["ADDITIONAL_YOU_CHAT_PERMISSIONS"] = new_you_chat_perms
    cfg["REPLY_PREFIX"] = new_reply_prefix
    cfg["SELF_CHAT_AGENT"] = new_self_chat_agent
    cfg["DEFAULT_AGENT"] = new_default_agent

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)
        console.print(f"[bold #a6e3a1]✓ WhatsApp configuration saved successfully to {config_path.name}[/bold #a6e3a1]\n")
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Error saving WhatsApp config: {e}[/bold #f38ba8]\n")

def build_web_ui(web_ui_dir):
    console.print(f"\n[bold #f9e2af]Building web-ui...[/bold #f9e2af]")
    try:
        console.print("[bold #585b70]Running npm install...[/bold #585b70]")
        subprocess.run(["npm", "install"], cwd=web_ui_dir, shell=True, check=True)
        
        console.print("[bold #585b70]Running npm run build...[/bold #585b70]")
        subprocess.run(["npm", "run", "build"], cwd=web_ui_dir, shell=True, check=True)
        
        console.print("[bold #a6e3a1]✓ web-ui built successfully.[/bold #a6e3a1]")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold #f38ba8]✗ Error building web-ui: command exited with status {e.returncode}[/bold #f38ba8]\n")
    except FileNotFoundError:
        console.print("[bold #f38ba8]✗ Error building web-ui: 'npm' was not found. Please install Node.js and npm.[/bold #f38ba8]\n")
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Error building web-ui: {e}[/bold #f38ba8]\n")

def get_persistent_openai_key():
    # 1. Check config.yaml
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                val = cfg.get("OPENAI_API_KEY")
                if val:
                    return val
        except Exception:
            pass

    # 2. Check current process env
    val = os.environ.get("OPENAI_API_KEY")
    if val:
        return val

    # 3. Check platform-specific persistent env
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                val, _ = winreg.QueryValueEx(key, "OPENAI_API_KEY")
                if val:
                    return val
        except Exception:
            pass
    else:
        # Check ~/.bashrc, ~/.zshrc, ~/.profile
        for filename in [".zshrc", ".bashrc", ".profile"]:
            path = Path.home() / filename
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("export OPENAI_API_KEY="):
                                val = line.split("=", 1)[1].strip()
                                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                                    val = val[1:-1]
                                if val:
                                    return val
                except Exception:
                    pass
    return None

def save_openai_key(key_value):
    # 1. Update config.yaml
    if not CONFIG_FILE.exists() and EXAMPLE_FILE.exists():
        try:
            shutil.copy(EXAMPLE_FILE, CONFIG_FILE)
            console.print(f"[bold #a6e3a1]✓ Copied config.yaml.example to config.yaml[/bold #a6e3a1]")
        except Exception as e:
            console.print(f"[bold #f38ba8]✗ Error copying main config: {e}[/bold #f38ba8]")

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            
            update_line_config(lines, "OPENAI_API_KEY", key_value)
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            console.print(f"[bold #a6e3a1]✓ Saved OPENAI_API_KEY to {CONFIG_FILE.name}[/bold #a6e3a1]")
        except Exception as e:
            console.print(f"[bold #f38ba8]✗ Error writing key to config.yaml: {e}[/bold #f38ba8]")

    # Update active process env
    os.environ["OPENAI_API_KEY"] = key_value

    # 2. Save persistently to environment path/variables
    if sys.platform == "win32":
        env = os.environ.copy()
        env["NEW_KEY"] = key_value
        cmd = "[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $env:NEW_KEY, 'User')"
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], env=env, check=True)
            console.print("[bold #a6e3a1]✓ Saved OPENAI_API_KEY to Windows User environment variables.[/bold #a6e3a1]")
        except Exception as e:
            console.print(f"[bold #f38ba8]✗ Failed to save OPENAI_API_KEY to Windows environment: {e}[/bold #f38ba8]")
    else:
        export_line = f'export OPENAI_API_KEY="{key_value}"'
        files_updated = []
        for filename in [".zshrc", ".bashrc", ".profile"]:
            path = Path.home() / filename
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    
                    found = False
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith("export OPENAI_API_KEY="):
                            new_lines.append(export_line + "\n")
                            found = True
                        else:
                            new_lines.append(line)
                    if not found:
                        if new_lines and not new_lines[-1].endswith("\n"):
                            new_lines.append("\n")
                        new_lines.append(export_line + "\n")
                    
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                    files_updated.append(filename)
                except Exception as e:
                    console.print(f"[bold #f38ba8]✗ Failed to update {filename}: {e}[/bold #f38ba8]")
        
        if files_updated:
            console.print(f"[bold #a6e3a1]✓ Saved OPENAI_API_KEY to: {', '.join(files_updated)}[/bold #a6e3a1]")
        else:
            console.print("[bold #f9e2af]! No shell profile files (.zshrc, .bashrc, .profile) found to write OPENAI_API_KEY environment variable.[/bold #f9e2af]")

def change_api_keys():
    current_key = get_persistent_openai_key()
    
    if current_key:
        masked_key = current_key
        if len(current_key) > 8:
            masked_key = current_key[:6] + "..." + current_key[-4:]
        
        console.print(f"\n[bold #cdd6f4]OpenAI API Key is currently set to: [/bold #cdd6f4][bold #89b4fa]{masked_key}[/bold #89b4fa]")
        
        change = ask_with_tick(
            questionary.confirm(
                "Would you like to change your OpenAI API Key?",
                default=False,
                style=tui_style
            ),
            "Would you like to change your OpenAI API Key?"
        )
        
        if not change:
            return
    else:
        console.print("\n[bold #f9e2af]! OpenAI API Key is currently unset.[/bold #f9e2af]")
    
    new_key = ask_with_tick(
        questionary.text(
            "Enter your OpenAI API Key:",
            style=tui_style
        ),
        "Enter your OpenAI API Key:"
    ).strip()
    
    if new_key:
        save_openai_key(new_key)
    else:
        console.print("[bold #f38ba8]✗ OpenAI API Key cannot be empty. No changes made.[/bold #f38ba8]")

def connect_to_whatsapp(whatsapp_dir):
    import sqlite3
    db_path = whatsapp_dir / "whatsapp_session.db"
    qr_path = whatsapp_dir / "whatsapp_qr.png"
    qr_txt_path = whatsapp_dir / "whatsapp_qr.txt"
    log_file_path = whatsapp_dir / "whatsapp.log"

    #console.print("\n[bold #89b4fa]=== WhatsApp Connection Utility ===[/bold #89b4fa]\n")
    print("")

    # Helper function to perform system-wide process termination
    def force_kill_system_processes():
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["powershell", "-Command", "Get-CimInstance Win32_Process -Filter \"CommandLine LIKE '%whatsapp.py%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
            try:
                subprocess.run(
                    ["wmic", "process", "where", "CommandLine like '%whatsapp.py%'", "call", "terminate"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        else:
            try:
                subprocess.run(["pkill", "-f", "whatsapp.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    # 1. Delete the current whatsapp_session.db file
    if db_path.exists():
        try:
            db_path.unlink()
            console.print("[bold #a6e3a1]✓ Deleted existing WhatsApp session database.[/bold #a6e3a1]")
        except Exception as e:
            console.print(f"[bold #f38ba8]✗ Failed to delete session database: {e}[/bold #f38ba8]")
    
    # Also delete existing QR assets and log file to avoid stale states
    for p in (qr_path, qr_txt_path):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    if log_file_path.exists():
        try:
            log_file_path.unlink()
        except Exception:
            pass

    # 2. Stop whatsapp.py if it is running
    console.print("[bold #585b70]Stopping any running whatsapp.py processes...[/bold #585b70]")
    force_kill_system_processes()

    # Give it a short pause to ensure processes are cleaned up
    time.sleep(1)

    # 3. Start whatsapp.py
    console.print("[bold #585b70]Starting whatsapp.py as a background process...[/bold #585b70]")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    proc = None
    try:
        f_log = open(log_file_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-u", "whatsapp.py"],
            cwd=str(whatsapp_dir),
            stdout=f_log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags
        )
    except Exception as e:
        console.print(f"[bold #f38ba8]✗ Failed to start whatsapp.py: {e}[/bold #f38ba8]")
        return

    # Helper function to check if database has authenticated device
    def is_authenticated():
        if not db_path.exists():
            return False
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='whatsmeow_device'")
            if not cursor.fetchone():
                conn.close()
                return False
            cursor.execute("SELECT * FROM whatsmeow_device")
            rows = cursor.fetchall()
            conn.close()
            return len(rows) > 0
        except Exception:
            return False

    # 4. Wait till \sub-programs\whatsapp\whatsapp_qr.txt exists
    console.print("[bold #f9e2af]Waiting for WhatsApp QR Code to be generated...[/bold #f9e2af]")
    
    qr_opened = False
    time.sleep(0.5)  # Give process a moment to initialize the log file
    
    try:
        # Loop while either we don't have the QR code or we are not yet authenticated
        while True:
            # Check if process is dead
            if proc.poll() is not None:
                # If it died, read logs and print them to help the user diagnose the failure
                if log_file_path.exists():
                    try:
                        with open(log_file_path, "r", encoding="utf-8", errors="replace") as f_err:
                            console.print("\n[bold #f38ba8]Error Logs from whatsapp.py:[/bold #f38ba8]")
                            print(f_err.read())
                    except Exception:
                        pass
                console.print("\n[bold #f38ba8]✗ whatsapp.py process exited unexpectedly.[/bold #f38ba8]")
                f_log.close()
                return

            # Trigger QR Code viewer once the file is generated
            if not qr_opened and qr_txt_path.exists():
                qr_opened = True
                console.print(f"\n[bold #a6e3a1]✓ QR Code generated successfully![/bold #a6e3a1]\n")
                
                try:
                    import segno
                    with open(qr_txt_path, "rb") as f_txt:
                        data_qr = f_txt.read()
                    qr = segno.make_qr(data_qr)
                    console.print("[bold #89b4fa]Scan this QR code with WhatsApp on your phone (Linked Devices):[/bold #89b4fa]\n")
                    qr.terminal(compact=True, border=1)
                except Exception as e:
                    console.print(f"[bold #f38ba8]✗ Error rendering QR code in terminal: {e}[/bold #f38ba8]")

                console.print("\n[bold #585b70]Waiting for authentication...[/bold #585b70]")

            # Check for successful authentication
            if is_authenticated():
                console.print("\n[bold #a6e3a1]✓ Authentication detected! Finalizing connection...[/bold #a6e3a1]")
                for i in range(10, 0, -1):
                    #console.print(f"[bold #585b70]{i}...[/bold #585b70]", end=" ")
                    time.sleep(1.0)
                #console.print()
                break

            time.sleep(0.5)
    finally:
        f_log.close()

    console.print("\n[bold #a6e3a1]✓ WhatsApp session established successfully![/bold #a6e3a1]")

    # 5. Stop the background whatsapp.py process since setup is complete
    console.print("[bold #585b70]Stopping the background whatsapp.py process...[/bold #585b70]")
    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        except Exception:
            pass
    force_kill_system_processes()

    # Delete the QR code files after finishing
    for p in (qr_path, qr_txt_path):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    console.print("[bold #a6e3a1]✓ Cleaned up WhatsApp QR code assets.[/bold #a6e3a1]")

def main():
    # Print cool ASCII art banner
    print("")
    try:
        banner = pyfiglet.figlet_format("OpenDoor", font="ansi_shadow")
        console.print(f"[bold #89b4fa]{banner}[/bold #89b4fa]")
    except Exception:
        console.print("[bold #89b4fa]=== OpenDoor Setup Wizard ===[/bold #89b4fa]\n")
        
    console.print("[bold #89b4fa]OpenDoor setup and configuration tool[/bold #89b4fa]\n")

    # 1. Check sub-programs download status
    sub_programs_dirs = {
        "whatsapp": (PROJECT_ROOT / "sub-programs" / "whatsapp", "whatsapp.py"),
        "web-ui": (PROJECT_ROOT / "sub-programs" / "web-ui", "package.json"),
        "TUI": (PROJECT_ROOT / "sub-programs" / "TUI", "TUI.py")
    }

    status_map = {}
    for name, (dir_path, check_file) in sub_programs_dirs.items():
        is_downloaded = dir_path.exists() and (dir_path / check_file).exists()
        status_map[name] = is_downloaded
        display_name = "WhatsApp" if name == "whatsapp" else name
        if is_downloaded:
            console.print(f"[bold #a6e3a1]✓ {display_name} sub-program is downloaded.[/bold #a6e3a1]")
        else:
            console.print(f"[bold #f38ba8]✗ {display_name} sub-program is not downloaded.[/bold #f38ba8]")

    # 2. Check and copy configs if missing
    # Main config
    console.print(f"\n[bold #585b70]Locating main configuration files...[/bold #585b70]")
    console.print(f"  Main config path: {CONFIG_FILE}")
    console.print(f"  Main config example: {EXAMPLE_FILE}")
    
    if not CONFIG_FILE.exists():
        console.print(f"[bold #f9e2af]! Main config.yaml not found. Attempting to copy from config.yaml.example...[/bold #f9e2af]")
        if EXAMPLE_FILE.exists():
            try:
                shutil.copy(EXAMPLE_FILE, CONFIG_FILE)
                console.print(f"[bold #a6e3a1]✓ Copied config.yaml.example to config.yaml[/bold #a6e3a1]")
            except Exception as e:
                console.print(f"[bold #f38ba8]✗ Error copying main config: {e}[/bold #f38ba8]")
        else:
            console.print(f"[bold #f38ba8]✗ Error: Main config template (config.yaml.example) is missing![/bold #f38ba8]")
    else:
        console.print(f"[bold #a6e3a1]✓ Main config.yaml exists.[/bold #a6e3a1]")

    # WhatsApp config
    whatsapp_dir = sub_programs_dirs["whatsapp"][0]
    whatsapp_config_path = whatsapp_dir / "whatsapp_config.yaml"
    whatsapp_example_path = whatsapp_dir / "whatsapp_config.yaml.example"
    
    if status_map["whatsapp"]:
        console.print(f"[bold #585b70]Locating WhatsApp configuration files...[/bold #585b70]")
        console.print(f"  WhatsApp config path: {whatsapp_config_path}")
        console.print(f"  WhatsApp config example: {whatsapp_example_path}")
        
        if not whatsapp_config_path.exists():
            console.print(f"[bold #f9e2af]! whatsapp_config.yaml not found. Attempting to copy from whatsapp_config.yaml.example...[/bold #f9e2af]")
            if whatsapp_example_path.exists():
                try:
                    shutil.copy(whatsapp_example_path, whatsapp_config_path)
                    console.print(f"[bold #a6e3a1]✓ Copied whatsapp_config.yaml.example to whatsapp_config.yaml[/bold #a6e3a1]")
                except Exception as e:
                    console.print(f"[bold #f38ba8]✗ Error copying WhatsApp config: {e}[/bold #f38ba8]")
            else:
                console.print(f"[bold #f38ba8]✗ Error: WhatsApp config template (whatsapp_config.yaml.example) is missing![/bold #f38ba8]")
        else:
            console.print(f"[bold #a6e3a1]✓ whatsapp_config.yaml exists.[/bold #a6e3a1]")
            
    # Main Menu Loop
    while True:
        print("")
        whatsapp_downloaded = whatsapp_dir.exists() and (whatsapp_dir / "whatsapp.py").exists()
        
        choices = [
            "Edit config",
            "Change API Keys",
            "Install sub-programs"
        ]
        if whatsapp_downloaded:
            choices.append("Connect to WhatsApp")
        choices.append("Exit")

        action = ask_with_tick(
            questionary.select(
                "What would you like to do?",
                choices=choices,
                style=tui_style
            ),
            "What would you like to do?"
        )

        if action in ("Cancel", "Exit"):
            break

        elif action == "Change API Keys":
            change_api_keys()

        elif action == "Connect to WhatsApp":
            connect_to_whatsapp(whatsapp_dir)

        elif action == "Edit config":
            while True:
                print("")
                # Recalculate whatsapp download status in case they downloaded it in this session
                whatsapp_downloaded_now = whatsapp_dir.exists() and (whatsapp_dir / "whatsapp.py").exists()
                
                edit_choices = ["Main System Config (config.yaml)"]
                if whatsapp_downloaded_now:
                    edit_choices.append("WhatsApp Gateway Config (whatsapp_config.yaml)")
                edit_choices.append("Back")

                choice = ask_with_tick(
                    questionary.select(
                        "Select a configuration to edit:",
                        choices=edit_choices,
                        style=tui_style
                    ),
                    "Select a configuration to edit:"
                )

                if choice == "Back":
                    break
                elif choice == "Main System Config (config.yaml)":
                    edit_main_config()
                elif choice == "WhatsApp Gateway Config (whatsapp_config.yaml)":
                    edit_whatsapp_config(whatsapp_config_path, whatsapp_example_path)

        elif action == "Install sub-programs":
            sub_programs_to_download = ask_with_tick(
                questionary.checkbox(
                    "Select sub-programs to enable/update (will download from GitHub):",
                    choices=["web-ui", "whatsapp", "TUI", "None"],
                    instruction="(Use arrow keys to move, <space> to select, <enter> to confirm)",
                    style=tui_style
                ),
                "Select sub-programs to enable/update (will download from GitHub):",
                answer_formatter=lambda ans: ", ".join(ans) if ans else "None"
            )
            
            if "None" in sub_programs_to_download:
                sub_programs_to_download = []
                
            if sub_programs_to_download:
                print("")
                sub_program_folder = PROJECT_ROOT / "sub-programs"
                
                # Clean up the legacy typo folder if it exists
                legacy_folder = PROJECT_ROOT / "sub-programss"
                if legacy_folder.exists():
                    try:
                        shutil.rmtree(legacy_folder)
                    except Exception:
                        pass
                        
                for i in sub_programs_to_download:
                    TARGET_FOLDER = f"sub-programs/{i}"
                    dest_dir = sub_program_folder / i
                    
                    current_ver = get_current_version()
                    if current_ver:
                        console.print(f"[bold #f9e2af]Downloading sub-program: {i} (version {current_ver})...[/bold #f9e2af]")
                        download_success = download_github_folder(TARGET_FOLDER, dest_dir, ref=current_ver)
                    else:
                        console.print(f"[bold #f9e2af]Downloading sub-program: {i}...[/bold #f9e2af]")
                        download_success = download_github_folder(TARGET_FOLDER, dest_dir)
                    
                    if download_success:
                        console.print(f"[bold #a6e3a1]✓ {i} downloaded/updated successfully.[/bold #a6e3a1]")
                        # Update status map for next loops
                        if i in sub_programs_dirs:
                            status_map[i] = True
                            
                        if i == "web-ui":
                            build_web_ui(dest_dir)
                    else:
                        console.print(f"[bold #f38ba8]✗ Failed to download/update {i}.[/bold #f38ba8]")
                        
                    print("")

                # If WhatsApp was downloaded, check and copy default config if needed
                whatsapp_downloaded_now = whatsapp_dir.exists() and (whatsapp_dir / "whatsapp.py").exists()
                if whatsapp_downloaded_now:
                    if not whatsapp_config_path.exists():
                        if whatsapp_example_path.exists():
                            try:
                                shutil.copy(whatsapp_example_path, whatsapp_config_path)
                                console.print(f"[bold #a6e3a1]✓ Copied default whatsapp_config.yaml for the newly downloaded WhatsApp sub-program.[/bold #a6e3a1]")
                                print("")
                            except Exception as e:
                                console.print(f"[bold #f38ba8]✗ Error copying WhatsApp config: {e}[/bold #f38ba8]")
                                print("")
                        else:
                            console.print(f"[bold #f38ba8]✗ Error: WhatsApp config template (whatsapp_config.yaml.example) is missing![/bold #f38ba8]")
                            print("")

                    # Prompt if they want to edit the newly downloaded WhatsApp config
                    if not status_map["whatsapp"]:
                        edit_new_whatsapp = ask_with_tick(
                            questionary.confirm(
                                "Would you like to configure the newly downloaded WhatsApp gateway now?",
                                default=True,
                                style=tui_style
                            ),
                            "Would you like to configure the newly downloaded WhatsApp gateway now?"
                        )
                        if edit_new_whatsapp:
                            edit_whatsapp_config(whatsapp_config_path, whatsapp_example_path)
                        else:
                            print("")
                        status_map["whatsapp"] = True

    console.print("\n[bold #a6e3a1]Configuration complete! Ready to start OpenDoor.[/bold #a6e3a1]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold #f38ba8]Setup cancelled by user.[/bold #f38ba8]")