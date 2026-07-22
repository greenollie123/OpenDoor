import os
import sys
import builtins
from pathlib import Path

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

# Add master-sub-agent to sys.path so runner.py and tool_loader.py can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
MASTER_SUB_AGENT_DIR = os.path.join(ROOT_DIR, "master-sub-agent")
if MASTER_SUB_AGENT_DIR not in sys.path:
    sys.path.insert(0, MASTER_SUB_AGENT_DIR)

@mcp.tool()
def call_master_subagent(task_instruction: str, agent_name: str = None) -> str:
    """Trigger the Master Subagent to orchestrate high-level multi-step objectives for an agent and return the final report.
    
    Args:
        task_instruction: Specific task description and instructions for the Master Subagent.
        agent_name: Target agent name on whose behalf the Master Subagent operates. If omitted, defaults to active agent.
    """
    req_ctx = getattr(builtins, "request_context", None) or globals().get("request_context")
    if not agent_name:
        if req_ctx and hasattr(req_ctx, "agent_name") and req_ctx.agent_name:
            agent_name = req_ctx.agent_name
        else:
            agent_name = "Terry"

    channel = getattr(req_ctx, "channel", "Web") if req_ctx else "Web"
    
    # Callback to stream UI progress updates
    def ui_progress_callback(event_type: str, content: str):
        add_ui_fn = globals().get("add_ui_update") or getattr(builtins, "add_ui_update", None)
        if add_ui_fn:
            try:
                add_ui_fn(event_type, channel, content, agent=agent_name)
            except Exception:
                pass

    try:
        from runner import run_master_subagent
        result = run_master_subagent(task_instruction=task_instruction, agent_name=agent_name, ui_callback=ui_progress_callback)
        return result
    except Exception as e:
        err_msg = f"[Error] Master Subagent execution error: {e}"
        ui_progress_callback("system", err_msg)
        return err_msg
