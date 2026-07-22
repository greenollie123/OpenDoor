import os

@mcp.tool()
def send_file_to_user(relative_path: str) -> str:
    """Send a file from the workspace back to the user via the current channel (e.g., WhatsApp).
    
    Args:
        relative_path: The file path relative to the workspace root.
    """
    target_abs_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not target_abs_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if not os.path.exists(target_abs_path):
        return f"Error: '{relative_path}' not found."
    
    return (f"File found at {target_abs_path}. "
            "IMPORTANT: To actually send this file to the user, you MUST include the following exact string anywhere in your final text response to them: "
            f"[SEND_FILE: {target_abs_path}]")
