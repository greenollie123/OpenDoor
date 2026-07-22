import os
import builtins

if 'mcp' not in globals() and not hasattr(builtins, 'mcp'):
    class MockMCP:
        def tool(self, name=None):
            def decorator(func):
                func._mcp_name = name or func.__name__
                return func
            return decorator
    mcp = MockMCP()
elif 'mcp' not in globals() and hasattr(builtins, 'mcp'):
    mcp = builtins.mcp

# Temporary task state for current session
TASK_QUEUE = []
TASK_MEMORIES = []

def _is_task_assigned_to_agent(assigned_agent: str, target_agent: str) -> bool:
    """Helper to check if a task's assigned_agent matches target_agent accounting for name variations."""
    if not assigned_agent or not target_agent:
        return False
    a1 = str(assigned_agent).lower().replace(" ", "").replace("_", "").replace("-", "")
    a2 = str(target_agent).lower().replace(" ", "").replace("_", "").replace("-", "")
    if a1 == a2:
        return True
    tester_aliases = ["tester", "debugger", "testeranddebugger", "testerdebugger"]
    if a1 in tester_aliases and a2 in tester_aliases:
        return True
    file_aliases = ["filemanager", "file", "filemgr"]
    if a1 in file_aliases and a2 in file_aliases:
        return True
    system_aliases = ["systemmanager", "system", "sysmgr"]
    if a1 in system_aliases and a2 in system_aliases:
        return True
    master_aliases = ["main", "master", "masteragent", "mainagent", "terry"]
    if a1 in master_aliases and a2 in master_aliases:
        return True
    return False

def get_artifacts_dir() -> str:
    artifacts_dir = getattr(builtins, "ARTIFACTS_DIR", None)
    if not artifacts_dir:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        artifacts_dir = os.path.abspath(os.path.join(root_dir, "..", "master", "working", "artifacts"))
    os.makedirs(artifacts_dir, exist_ok=True)
    return artifacts_dir

@mcp.tool()
def clear_shared_artifacts() -> str:
    """Deletes all temporary shared artifacts from the artifacts/ directory."""
    artifacts_dir = get_artifacts_dir()
    if not os.path.exists(artifacts_dir):
        return "Artifacts directory does not exist."
    count = 0
    for filename in os.listdir(artifacts_dir):
        filepath = os.path.join(artifacts_dir, filename)
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
                count += 1
            except Exception:
                pass
    return f"Successfully deleted {count} temporary artifact(s) from 'artifacts/'."

@mcp.tool()
def create_todo_list(tasks: list) -> str:
    """Initializes the high-level roadmap/todo list for the user request and clears temporary artifacts.
    
    Args:
        tasks: A list of task description strings.
    """
    global TASK_QUEUE
    TASK_QUEUE = []
    clear_shared_artifacts()
    for idx, t in enumerate(tasks, 1):
        TASK_QUEUE.append({
            "id": idx,
            "description": str(t),
            "status": "pending",
            "assigned_agent": "Main",
            "result_summary": ""
        })
    return f"Successfully created todo list with {len(TASK_QUEUE)} tasks."

@mcp.tool()
def update_task_status(task_id: int, status: str) -> str:
    """Tracks implementation progress by updating task status.
    
    Args:
        task_id: The integer ID of the task.
        status: The new status ('pending', 'in_progress', 'completed').
    """
    for task in TASK_QUEUE:
        if task["id"] == task_id:
            task["status"] = status
            return f"Task {task_id} status updated to '{status}'."
    return f"Error: Task ID {task_id} not found."

@mcp.tool()
def read_my_tasks(agent_name: str = None) -> str:
    """Read active tasks assigned specifically to the calling agent or for the session.
    
    Args:
        agent_name: Optional name of the agent ('Coder', 'File Manager', 'Researcher', 'System Manager', 'Tester and Debugger', 'Master').
    """
    if not agent_name:
        agent_name = getattr(builtins, "CURRENT_AGENT_NAME", None) or os.environ.get("CURRENT_AGENT_NAME") or "Master"

    if not TASK_QUEUE:
        return "No tasks currently in the todo list."

    is_master = _is_task_assigned_to_agent(agent_name, "Master") or str(agent_name).lower() in ["terry", "main", "master"]

    matching_tasks = []
    for t in TASK_QUEUE:
        if is_master or _is_task_assigned_to_agent(t.get("assigned_agent", ""), agent_name):
            matching_tasks.append(t)

    if not matching_tasks:
        return f"No tasks currently assigned to agent '{agent_name}'."

    lines = [f"Current Tasks Roadmap for '{agent_name}':" if not is_master else "Current Master Tasks Roadmap:"]
    for t in matching_tasks:
        status_symbol = "[x]" if t["status"] == "completed" else ("[/]" if t["status"] == "in_progress" else "[ ]")
        lines.append(f"{status_symbol} Task #{t['id']}: {t['description']} (Status: {t['status']}, Agent: {t['assigned_agent']})")
        if t.get("result_summary"):
            lines.append(f"    Result: {t['result_summary']}")
    return "\n".join(lines)

@mcp.tool()
def add_subtask_to_master(new_task_description: str, suggested_agent: str = "Main", reason: str = "") -> str:
    """Pass-back mechanism to inject a new follow-up subtask into the Master queue.
    
    Args:
        new_task_description: Description of the new subtask.
        suggested_agent: Suggested agent role ('Coder', 'FileManager', 'Researcher', 'SystemManager', 'Tester', 'Main').
        reason: Reason for adding this subtask.
    """
    new_id = len(TASK_QUEUE) + 1
    task_entry = {
        "id": new_id,
        "description": new_task_description,
        "status": "pending",
        "assigned_agent": suggested_agent,
        "result_summary": f"Added reason: {reason}" if reason else ""
    }
    TASK_QUEUE.append(task_entry)
    return f"Successfully added subtask #{new_id}: '{new_task_description}' for agent '{suggested_agent}'."

@mcp.tool()
def mark_task_complete(task_id: int, result_summary: str = "") -> str:
    """Signals completion of a task and records a result summary.
    
    Args:
        task_id: The integer ID of the completed task.
        result_summary: Clean, compact summary of the output or changes made.
    """
    for task in TASK_QUEUE:
        if task["id"] == task_id:
            task["status"] = "completed"
            task["result_summary"] = result_summary
            return f"Task #{task_id} marked as completed."
    return f"Error: Task ID {task_id} not found."

@mcp.tool()
def task_complete(summary: str) -> str:
    """Gracefully terminates task execution and passes the final summary back.
    
    Args:
        summary: Final overall summary of all completed work.
    """
    return f"Task Session Complete: {summary}"

@mcp.tool()
def task_failed(reason: str, logs: str = "") -> str:
    """Reports an error or unresolvable blocker to terminate or pivot task.
    
    Args:
        reason: Reason for failure.
        logs: Optional log output or error stack trace.
    """
    msg = f"Task Failed: {reason}"
    if logs:
        msg += f"\nLogs:\n{logs}"
    return msg
