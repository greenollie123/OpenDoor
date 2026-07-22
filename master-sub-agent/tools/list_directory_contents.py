import os

@mcp.tool()
def list_directory_contents(relative_path: str = "") -> str:
    """List files directly within a directory inside the workspace, showing sub-directories as workspace-relative paths. It does not list the contents of sub-directories.
    
    Args:
        relative_path: The relative path to list from the root of the working folder. Leave blank or use '' for root.
    """
    target_abs_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    workspace_abs_path = os.path.abspath(AI_WORKSPACE_DIR)
    if not target_abs_path.startswith(workspace_abs_path):
        return "Error: Access denied."
    if not os.path.exists(target_abs_path):
        return f"Error: Directory '{relative_path}' not found."
    if not os.path.isdir(target_abs_path):
        return f"Error: Path '{relative_path}' is a file, not a directory."
    items = os.listdir(target_abs_path)
    if not items:
        return f"Directory '{relative_path if relative_path else '.'}' is empty."
    output = []
    for item in items:
        item_abs_path = os.path.join(target_abs_path, item)
        if os.path.isdir(item_abs_path):
            rel_from_workspace = os.path.relpath(item_abs_path, workspace_abs_path).replace(os.sep, "/")
            output.append(f"- {rel_from_workspace}/")
        else:
            output.append(f"- {item}")
    return "\n".join(output)
