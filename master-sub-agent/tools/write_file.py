import os

@mcp.tool()
def write_file(relative_path: str, content: str) -> str:
    """Write or overwrite a file.
    
    Args:
        relative_path: The relative path of the file to write. This MUST be a file path including the filename, not a directory.
        content: The content to write inside the file.
    """
    safe_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not safe_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if os.path.isdir(safe_path):
        return f"Error: '{relative_path}' is a directory. Please specify a full file path, including the filename."
    with open(safe_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"Successfully wrote to {relative_path}"
