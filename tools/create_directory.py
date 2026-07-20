import os

@mcp.tool()
def create_directory(relative_path: str, directory_name: str) -> str:
    """Create a new folder/directory in the workspace.
    
    Args:
        relative_path: The path where you want to create the folder (relative to workspace root). Use '.' for root.
        directory_name: The name of the new folder.
    """
    target_dir = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path, directory_name))
    if not target_dir.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied. Cannot create directories outside the workspace."
    try:
        os.makedirs(target_dir, exist_ok=True)
        return f"Successfully created directory: {os.path.relpath(target_dir, AI_WORKSPACE_DIR)}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"
