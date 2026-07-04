@mcp.tool()
def read_archived_session_tutorial(agent_name: str = "Terry") -> str:
    """Shows the exact multi-step instructions for reading an archived session.
    
    Args:
        agent_name: The name of the agent whose archived sessions you want to read.
    """
    return (
        "To successfully locate and read an archived session without losing structural context, execute these steps sequentially:\n"
        f"1. Invoke 'list_directory' tool with relative_path='agents/{agent_name}/archived-sessions' to display available sessions.\n"
        f"2. Depending on what the user requested, invoke 'read_file' on 'agents/{agent_name}/archived-sessions/recent.md' or a specific archived session file in that folder.\n"
        "3. Output the necessary information to the user."
    )

@mcp.tool()
def read_create_tool_tutorial(agent_name: str = "Terry") -> str:
    """Shows the exact multi-step instructions for creating a new tool.
    
    Args:
        agent_name: The name of the agent whose archived sessions you want to read.
    """
    return (
        "To create tools, read `custom-tools\CUSTOM_TOOLS_CREATION_TUTORIAL.md` first."
    )
