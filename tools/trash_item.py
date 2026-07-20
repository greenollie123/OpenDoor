import os
import shutil
from datetime import datetime

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
