import os

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
