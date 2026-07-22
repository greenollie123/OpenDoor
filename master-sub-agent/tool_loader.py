import os
import sys
import glob
import json
import inspect
import typing
import builtins
import importlib.util

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
# Base project root directory (one level up from master-sub-agent)
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(ROOT_DIR, ".."))
MASTER_DIR = os.path.join(PROJECT_ROOT_DIR, "master")
AI_WORKSPACE_DIR = os.path.join(MASTER_DIR, "working")
FILE_DIR = os.path.join(MASTER_DIR, "files")
RUBBISH_BIN_DIR = os.path.join(FILE_DIR, "rubbish_bin")
ARTIFACTS_DIR = os.path.join(AI_WORKSPACE_DIR, "artifacts")

os.makedirs(AI_WORKSPACE_DIR, exist_ok=True)
os.makedirs(RUBBISH_BIN_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

class MockMCP:
    def tool(self, name=None):
        def decorator(func):
            func._mcp_name = name or func.__name__
            return func
        return decorator

mock_mcp = MockMCP()
builtins.mcp = mock_mcp
builtins.AI_WORKSPACE_DIR = AI_WORKSPACE_DIR
builtins.RUBBISH_BIN_DIR = RUBBISH_BIN_DIR
builtins.ARTIFACTS_DIR = ARTIFACTS_DIR

CURRENT_AGENT_NAME = "Terry"

def set_active_workspace(agent_name: str = "Terry", custom_workspace: str = None) -> str:
    """Set the active workspace directory to the full master/working directory."""
    global AI_WORKSPACE_DIR, CURRENT_AGENT_NAME
    CURRENT_AGENT_NAME = agent_name
    builtins.CURRENT_AGENT_NAME = agent_name
    if custom_workspace:
        AI_WORKSPACE_DIR = os.path.abspath(custom_workspace)
    else:
        AI_WORKSPACE_DIR = os.path.abspath(os.path.join(MASTER_DIR, "working"))
    
    os.makedirs(AI_WORKSPACE_DIR, exist_ok=True)
    builtins.AI_WORKSPACE_DIR = AI_WORKSPACE_DIR
    return AI_WORKSPACE_DIR

def ask_for_consent(title: str, description: str) -> str:
    """Ask the user for consent or approval before carrying out an action."""
    import inspect
    import requests
    caller_tool_name = None
    try:
        for frame_info in inspect.stack():
            func_name = frame_info.function
            if frame_info.filename.endswith(".py") and "tools" in frame_info.filename:
                caller_tool_name = func_name
                break
    except Exception:
        pass
        
    agent_name = (
        getattr(builtins, "CURRENT_AGENT_NAME", None) or 
        globals().get("CURRENT_AGENT_NAME") or 
        getattr(getattr(builtins, "request_context", None), "agent_name", None) or 
        "Terry"
    )
            
    try:
        resp = requests.post(
            "http://127.0.0.1:5050/api/request_consent",
            json={
                "title": title,
                "description": description,
                "tool_name": caller_tool_name,
                "agent_name": agent_name
            },
            timeout=300
        )
        if resp.status_code == 200:
            return resp.json().get("action", "denied")
    except Exception as e:
        print(f"[-] Error requesting consent: {e}")
    return "denied"

def get_embedding(text: str) -> list:
    return []

def cosine_similarity(v1: list, v2: list) -> float:
    return 0.0

builtins.ask_for_consent = ask_for_consent
builtins.get_embedding = get_embedding
builtins.cosine_similarity = cosine_similarity

def python_type_to_json_type(py_type):
    if py_type == str or py_type == 'str':
        return {"type": "string"}
    elif py_type == int or py_type == 'int':
        return {"type": "integer"}
    elif py_type == float or py_type == 'float':
        return {"type": "number"}
    elif py_type == bool or py_type == 'bool':
        return {"type": "boolean"}
    elif py_type == list or py_type == 'list':
        return {"type": "array", "items": {"type": "string"}}
    elif typing.get_origin(py_type) is list:
        return {"type": "array", "items": {"type": "string"}}
    else:
        return {"type": "string"}

def func_to_openai_tool(func):
    name = getattr(func, '_mcp_name', func.__name__)
    doc = inspect.getdoc(func) or ""
    
    desc = doc.split("Args:")[0].strip() if "Args:" in doc else doc.strip()
    
    param_docs = {}
    if "Args:" in doc:
        args_part = doc.split("Args:")[1]
        if "Returns:" in args_part:
            args_part = args_part.split("Returns:")[0]
        if "Notes:" in args_part:
            args_part = args_part.split("Notes:")[0]
        for line in args_part.splitlines():
            line = line.strip()
            if ":" in line:
                p_name, p_desc = line.split(":", 1)
                param_docs[p_name.strip()] = p_desc.strip()

    sig = inspect.signature(func)
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name in ['self', 'cls']:
            continue
        p_type = param.annotation if param.annotation != inspect.Parameter.empty else str
        schema_prop = python_type_to_json_type(p_type)
        if param_name in param_docs:
            schema_prop["description"] = param_docs[param_name]
        properties[param_name] = schema_prop

        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc or f"Execute tool {name}",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }

SUBAGENT_TOOL_NAMES = {
    "Coder": [
        "read_file", "write_file", "file_patch_text", "file_add_line", "create_new_file",
        "list_skills", "read_skill",
        "read_my_tasks", "add_subtask_to_master", "mark_task_complete", "task_complete", "task_failed"
    ],
    "File Manager": [
        "list_directory_contents", "list_all_directory_contents", "create_directory", 
        "rename_item", "move_item", "read_file", "trash_item", "send_file_to_user",
        "list_skills", "read_skill",
        "read_my_tasks", "add_subtask_to_master", "mark_task_complete", "task_complete", "task_failed"
    ],
    "Researcher": [
        "web_search", "list_skills", "read_skill", "read_create_tool_tutorial", "read_file",
        "list_directory_contents", "list_all_directory_contents",
        "read_my_tasks", "add_subtask_to_master", "mark_task_complete", "task_complete", "task_failed"
    ],
    "System Manager": [
        "run_command", "restart_mcp_server", "add_memory", "remove_memory",
        "list_skills", "read_skill",
        "read_my_tasks", "add_subtask_to_master", "mark_task_complete", "task_complete", "task_failed"
    ],
    "Tester and Debugger": [
        "read_file", "run_command", "list_directory_contents", "list_all_directory_contents",
        "list_skills", "read_skill",
        "read_my_tasks", "add_subtask_to_master", "mark_task_complete", "task_complete", "task_failed"
    ]
}

MASTER_TOOL_NAMES = [
    "create_todo_list", "update_task_status", "clear_shared_artifacts", "read_file", "write_file", "call_subagent"
]

def load_all_tools():
    tools_dir = os.path.join(ROOT_DIR, "tools")
    loaded_functions = {}

    for filepath in sorted(glob.glob(os.path.join(tools_dir, "*.py"))):
        basename = os.path.basename(filepath)
        if basename.startswith("__"):
            continue
            
        module_name = f"tools.{basename[:-3]}"
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            mod.mcp = mock_mcp
            mod.AI_WORKSPACE_DIR = AI_WORKSPACE_DIR
            mod.RUBBISH_BIN_DIR = RUBBISH_BIN_DIR
            mod.ask_for_consent = ask_for_consent
            mod.get_embedding = get_embedding
            mod.cosine_similarity = cosine_similarity
            mod.os = os
            mod.json = json
            try:
                spec.loader.exec_module(mod)
                for attr in dir(mod):
                    fn = getattr(mod, attr)
                    if callable(fn) and hasattr(fn, '_mcp_name'):
                        tool_name = fn._mcp_name
                        loaded_functions[tool_name] = fn
            except Exception as e:
                print(f"[Tool Loader Warning] Error loading {basename}: {e}")

    return loaded_functions

def get_tools_for_agent(agent_name: str, all_functions: dict):
    """Returns (func_dict, schema_list) for a given agent name."""
    if agent_name == "Master":
        allowed_names = MASTER_TOOL_NAMES
    else:
        norm_name = None
        for k in SUBAGENT_TOOL_NAMES.keys():
            if k.lower().replace(" ", "") == agent_name.lower().replace(" ", ""):
                norm_name = k
                break
            if agent_name.lower() in ["tester", "debugger", "testeranddebugger"] and k == "Tester and Debugger":
                norm_name = k
                break
            if agent_name.lower() in ["filemanager", "file manager"] and k == "File Manager":
                norm_name = k
                break
            if agent_name.lower() in ["systemmanager", "system manager"] and k == "System Manager":
                norm_name = k
                break
        
        if not norm_name:
            raise ValueError(f"Unknown subagent name '{agent_name}'. Allowed: {list(SUBAGENT_TOOL_NAMES.keys())}")
        allowed_names = SUBAGENT_TOOL_NAMES[norm_name]

    agent_funcs = {}
    schemas = []
    for name in allowed_names:
        if name in all_functions:
            fn = all_functions[name]
            agent_funcs[name] = fn
            schemas.append(func_to_openai_tool(fn))
            
    return agent_funcs, schemas
