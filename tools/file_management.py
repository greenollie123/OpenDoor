@mcp.tool()
def rename_item(relative_path: str, new_name: str) -> str:
    """Rename a file or directory. Provide only the new name; the tool preserves the original file extension automatically.
    
    Args:
        relative_path: The current relative path of the file or directory.
        new_name: The new name (do not include extension for files).
    """
    abs_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not abs_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if not os.path.exists(abs_path):
        return f"Error: '{relative_path}' not found."
    directory = os.path.dirname(abs_path)
    if os.path.isdir(abs_path):
        new_full_path = os.path.join(directory, new_name)
    else:
        _, extension = os.path.splitext(abs_path)
        new_full_path = os.path.join(directory, f"{new_name}{extension}")
    try:
        os.rename(abs_path, new_full_path)
        return f"Successfully renamed to '{os.path.relpath(new_full_path, AI_WORKSPACE_DIR)}'"
    except Exception as e:
        return f"Error renaming: {str(e)}"

@mcp.tool()
def trash_item(relative_path: str) -> str:
    """Moves a file or folder to the rubbish bin. Use this if the user asks to delete, trash or remove a file.
    
    Args:
        relative_path: The path of the file or directory to trash, relative to the workspace root.
    """
    target_abs_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not target_abs_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if target_abs_path == os.path.abspath(AI_WORKSPACE_DIR):
        return "Error: Cannot trash the root workspace."
    if not os.path.exists(target_abs_path):
        return f"Error: '{relative_path}' not found."
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(target_abs_path)
    if os.path.isdir(target_abs_path):
        dest_name = f"{base_name}_{timestamp}"
    else:
        name_part, ext_part = os.path.splitext(base_name)
        dest_name = f"{name_part}_{timestamp}{ext_part}"
    dest_path = os.path.join(RUBBISH_BIN_DIR, dest_name)
    try:
        shutil.move(target_abs_path, dest_path)
        return f"Successfully moved '{relative_path}' to the rubbish bin."
    except Exception as e:
        return f"Error moving item to trash: {str(e)}"

@mcp.tool()
def create_new_file(relative_path: str, filename: str) -> str:
    """Create a new file (markdown, txt, python, etc.) in a specific directory.
    
    Args:
        relative_path: The directory to create the file in (relative to workspace root). Use '.' for root.
        filename: The name of the file including extension (e.g., 'notes.md', 'script.py').
    """
    target_dir = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    full_path = os.path.join(target_dir, filename)
    if not full_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied. Cannot create files outside the workspace."
    if not os.path.exists(target_dir):
        return f"Error: Directory '{relative_path}' not found."
    try:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write("")
        return f"Successfully created file: {os.path.relpath(full_path, AI_WORKSPACE_DIR)}"
    except Exception as e:
        return f"Error creating file: {str(e)}"

@mcp.tool()
def send_file_to_user(relative_path: str) -> str:
    """Send a file from the workspace back to the user via the current channel (e.g., WhatsApp).
    
    Args:
        relative_path: The file path relative to the workspace root.
    """
    target_abs_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not target_abs_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if not os.path.exists(target_abs_path):
        return f"Error: '{relative_path}' not found."
    
    return (f"File found at {target_abs_path}. "
            "IMPORTANT: To actually send this file to the user, you MUST include the following exact string anywhere in your final text response to them: "
            f"[SEND_FILE: {target_abs_path}]")
