import os

@mcp.tool()
def read_file(relative_path: str) -> str:
    """Read contents of a file.
    
    Args:
        relative_path: The relative path of the file to read.
    """
    safe_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not safe_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if not os.path.exists(safe_path):
        return f"Error: File '{relative_path}' not found."
    with open(safe_path, 'r', encoding='utf-8') as f:
        return f.read()
