import os

def get_skill_content(skill_name: str) -> str:
    workspace_dir = globals().get("AI_WORKSPACE_DIR")
    if not workspace_dir:
        # Fallback to resolving relative to the file's location
        workspace_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "master", "working")
    
    skill_file = os.path.join(workspace_dir, "skills", skill_name, "SKILL.md")
    if not os.path.exists(skill_file):
        return f"Error: Skill '{skill_name}' not found."
    
    try:
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Return the body of the skill (strip frontmatter)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content.strip()
    except Exception as e:
        return f"Error reading skill '{skill_name}': {str(e)}"

@mcp.tool()
def read_create_tool_tutorial(agent_name: str = "Terry") -> str:
    """Shows the exact multi-step instructions for creating a new tool.
    
    Args:
        agent_name: The name of the agent whose archived sessions you want to read.
    """
    return get_skill_content("create-tool")
