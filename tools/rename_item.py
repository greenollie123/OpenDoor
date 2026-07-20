import os

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
