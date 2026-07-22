import builtins
import subprocess

@mcp.tool()
def run_command(command: str) -> str:
    """Run a general terminal command (like pip install) and return its output.
    
    Args:
        command: The terminal command line string to run.
    """
    consent_fn = globals().get("ask_for_consent") or getattr(builtins, "ask_for_consent", None)
    if consent_fn:
        approval = consent_fn("Terminal Command", command)
        if approval != "approved":
            return "Error: Command execution denied by user."
            
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            cwd=AI_WORKSPACE_DIR,
            timeout=180,
            stdin=subprocess.DEVNULL
        )
        
        output = ""
        if result.stdout:
            output += f"Output:\n{result.stdout}\n"
        if result.stderr:
            output += f"Errors/Warnings:\n{result.stderr}\n"
            
        if not output.strip():
            return "Command executed successfully with no output."
            
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command execution timed out after 3 minutes."
    except Exception as e:
        return f"Error executing command: {e}"
