import os
import yaml

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
def read_archived_session_tutorial(agent_name: str = "Terry") -> str:
    """Shows the exact multi-step instructions for reading an archived session.
    
    Args:
        agent_name: The name of the agent whose archived sessions you want to read.
    """
    content = get_skill_content("read-archived-session")
    return content.replace("{agent_name}", agent_name)

@mcp.tool()
def read_create_tool_tutorial(agent_name: str = "Terry") -> str:
    """Shows the exact multi-step instructions for creating a new tool.
    
    Args:
        agent_name: The name of the agent whose archived sessions you want to read.
    """
    return get_skill_content("create-tool")

@mcp.tool()
def list_skills() -> str:
    """Lists all available custom skills in the workspace."""
    workspace_dir = globals().get("AI_WORKSPACE_DIR")
    if not workspace_dir:
        workspace_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "master", "working")
    
    skills_dir = os.path.join(workspace_dir, "skills")
    if not os.path.exists(skills_dir):
        return "No skills directory found."
    
    skills = []
    try:
        for skill_name in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, skill_name)
            if os.path.isdir(skill_path):
                skill_file = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(skill_file):
                    desc = ""
                    with open(skill_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            try:
                                fm = yaml.safe_load(parts[1])
                                if isinstance(fm, dict):
                                    desc = fm.get("description", "")
                            except Exception:
                                pass
                    skills.append(f"- **{skill_name}**: {desc if desc else 'No description'}")
        if not skills:
            return "No skills found."
        return "Available Skills:\n" + "\n".join(skills)
    except Exception as e:
        return f"Error listing skills: {str(e)}"

@mcp.tool()
def read_skill(skill_name: str) -> str:
    """Reads the detailed instructions of a specific skill.
    
    Args:
        skill_name: The name of the skill to read.
    """
    return get_skill_content(skill_name)

