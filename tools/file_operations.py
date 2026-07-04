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

@mcp.tool()
def file_patch_text(relative_path: str, search_text: str, replace_text: str) -> str:
    """Surgically find and replace a block of text.
    
    Args:
        relative_path: The relative path of the file to patch.
        search_text: The exact block of text to search for and replace.
        replace_text: The replacement text.
    """
    safe_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not safe_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if not os.path.exists(safe_path):
        return f"Error: File '{relative_path}' not found."
    with open(safe_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if search_text not in content:
        return "Error: Target text block not found."
    updated_content = content.replace(search_text, replace_text, 1)
    with open(safe_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    return f"Successfully patched '{relative_path}'."

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


