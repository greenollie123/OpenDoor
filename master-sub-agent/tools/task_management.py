import os

# Temporary task state for current session
TASK_QUEUE = []
TASK_MEMORIES = []

@mcp.tool()
def create_todo_list(tasks: list) -> str:
    """Initializes the high-level roadmap/todo list for the user request.
    
    Args:
        tasks: A list of task description strings.
    """
    global TASK_QUEUE
    TASK_QUEUE = []
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
def read_my_tasks() -> str:
    """Read active tasks, roadmap status, and contextual goals for the session."""
    if not TASK_QUEUE:
        return "No tasks currently in the todo list."
    lines = ["Current Tasks Roadmap:"]
    for t in TASK_QUEUE:
        status_symbol = "[x]" if t["status"] == "completed" else ("[/]" if t["status"] == "in_progress" else "[ ]")
        lines.append(f"{status_symbol} Task #{t['id']}: {t['description']} (Status: {t['status']}, Agent: {t['assigned_agent']})")
        if t["result_summary"]:
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
