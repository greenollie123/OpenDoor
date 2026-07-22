import os

@mcp.tool()
def list_all_directory_contents(relative_path: str = ".") -> str:
    """Lists all files in the workspace or a specific subdirectory.
    
    Args:
        relative_path: The subdirectory to list (e.g., 'projects'). Defaults to '.' for the root.
    """
    if relative_path == "." or not relative_path:
        target_dir = AI_WORKSPACE_DIR
    else:
        target_dir = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not target_dir.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied. Path outside of workspace."
    if not os.path.exists(target_dir):
        return f"Error: Directory '{relative_path}' does not exist."
    output = []
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, AI_WORKSPACE_DIR)
            output.append(rel_path.replace(os.sep, "/"))
    if not output:
        return "The directory is empty."
    output.sort()
    return "\n".join(output)
