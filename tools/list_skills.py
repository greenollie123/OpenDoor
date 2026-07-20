import os
import yaml

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
