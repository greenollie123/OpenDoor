import os

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
