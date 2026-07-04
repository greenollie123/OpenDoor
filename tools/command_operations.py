import subprocess

@mcp.tool()
def run_python_script(relative_path: str, args: str = "") -> str:
    """Run a Python script and return its output.
    
    Args:
        relative_path: The relative path of the Python file to run.
        args: Optional command line arguments to pass to the script.
    """
    safe_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not safe_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if not os.path.exists(safe_path):
        return f"Error: Script '{relative_path}' not found."
    
    command = f"python \"{safe_path}\""
    if args:
        command += f" {args}"
        
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
            
        if result.returncode != 0:
            output += f"\nScript exited with error code {result.returncode}."
            
        if not output.strip():
            return "Script executed successfully with no output."
            
        return output
    except subprocess.TimeoutExpired:
        return "Error: Script execution timed out after 3 minutes."
    except Exception as e:
        return f"Error executing script: {e}"

@mcp.tool()
def run_command(command: str) -> str:
    """Run a general terminal command (like pip install) and return its output.
    
    Args:
        command: The terminal command line string to run.
    """
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
