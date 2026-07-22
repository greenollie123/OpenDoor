import os

@mcp.tool()
def file_add_line(relative_path: str, text: str) -> str:
    """Append a line to the bottom of a file. You must read the file first and follow the formatting of that file.
    
    Args:
        relative_path: The relative path of the file.
        text: The line text to append.
    """
    safe_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not safe_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    file_exists = os.path.exists(safe_path)
    with open(safe_path, 'a', encoding='utf-8') as f:
        if file_exists:
            with open(safe_path, 'r', encoding='utf-8') as fr:
                existing_content = fr.read()
                if existing_content and not existing_content.endswith('\n'):
                    f.write('\n')
        f.write(f"{text}\n")
    return f"Successfully added line to '{relative_path}'."
