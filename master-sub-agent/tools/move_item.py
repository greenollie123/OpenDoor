import os
import shutil


@mcp.tool()
def move_item(source_path: str, destination_path: str) -> str:
    """Move a file or directory from one path to another within the workspace.

    Args:
        source_path: Workspace-relative path of the file/dir to move.
        destination_path: Workspace-relative destination path. If the parent directory
            does not exist, it will be created.

    Returns:
        A success message or an error string.

    Notes:
        - Prevents moving items outside the workspace.
        - Uses shutil.move().
    """

    # Workspace root should match what other tools use.
    # Many tool modules rely on the runtime injecting AI_WORKSPACE_DIR and mcp.
    # We follow that pattern here.
    src_abs = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, source_path))
    dst_abs = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, destination_path))
    workspace_abs = os.path.abspath(AI_WORKSPACE_DIR)

    if not src_abs.startswith(workspace_abs + os.sep) and src_abs != workspace_abs:
        return "Error: Access denied. Source outside workspace."
    if not dst_abs.startswith(workspace_abs + os.sep) and dst_abs != workspace_abs:
        return "Error: Access denied. Destination outside workspace."

    if not os.path.exists(src_abs):
        return f"Error: Source '{source_path}' does not exist."

    try:
        os.makedirs(os.path.dirname(dst_abs) if os.path.splitext(dst_abs)[1] else dst_abs, exist_ok=True)
        shutil.move(src_abs, dst_abs)
        return f"Successfully moved '{source_path}' to '{destination_path}'."
    except Exception as e:
        return f"Error moving item: {str(e)}"
