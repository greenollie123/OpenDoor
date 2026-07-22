@mcp.tool()
def ask_for_consent_tool(title: str, description: str) -> str:
    """Ask the user for consent or approval before carrying out an action.
    
    Args:
        title: The title/summary of the action requiring approval.
        description: The detailed description or command to run.
    """
    return ask_for_consent(title, description)
