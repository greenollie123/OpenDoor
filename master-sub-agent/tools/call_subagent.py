import os
import json
import platform
import builtins
import yaml
import litellm

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

def get_user_os() -> str:
    override = os.environ.get("USER_OS")
    if override:
        return override
    return f"{platform.system()} {platform.release()} ({platform.machine()})"

def get_subagent_model_info():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    models_file = os.path.join(root_dir, "models.yaml")
    models_cfg = {}
    if os.path.exists(models_file):
        try:
            with open(models_file, "r", encoding="utf-8") as f:
                models_cfg = yaml.safe_load(f) or {}
        except Exception:
            pass
    model_info = models_cfg.get("DEFAULT_SUBAGENT_MODEL") or models_cfg.get("SUBAGENT_MODEL") or models_cfg.get("DEFAULT_MODEL") or {}
    model_name = model_info.get("model", "gpt-5.4-nano")
    api_key = model_info.get("api_key") or os.environ.get("OPENAI_API_KEY")
    api_base = model_info.get("api_base") or os.environ.get("OPENAI_API_BASE")
    return model_name, api_key, api_base

ALL_LOADED_TOOLS = {}
UI_CALLBACK = None


SUBAGENT_DIRECTORY_INFO = (
    "SYSTEM SUB-AGENT DIRECTORY (structure.md):\n"
    "You are operating within a multi-agent system alongside 4 other specialized sub-agents:\n"
    "1. 'Researcher': Web search (web_search), directory listing (list_directory_contents, list_all_directory_contents), skill definitions (list_skills, read_skill, read_create_tool_tutorial), and file reading. Check for useful tools and pass any that may be helpful to the main agent.\n"
    "2. 'Coder': Writing, creating, patching, and editing code files (read_file, write_file, file_patch_text, file_add_line, create_new_file, list_skills, read_skill).\n"
    "3. 'File Manager': Managing directory structure, creating directories, moving, renaming, and trashing files (list_directory_contents, list_all_directory_contents, create_directory, rename_item, move_item, trash_item, send_file_to_user, list_skills, read_skill).\n"
    "4. 'System Manager': Terminal command execution (run_command), environment control, service state (restart_mcp_server), and memory management (add_memory, remove_memory, list_skills, read_skill).\n"
    "5. 'Tester and Debugger': Executing tests via commands (run_command), inspecting logs, checking workspace directories (list_directory_contents, list_all_directory_contents), verifying code correctness, and reading skill definitions (list_skills, read_skill).\n\n"
    "TRANSIENT ARTIFACTS USAGE RULE:\n"
    "The 'artifacts/' directory is reserved strictly for temporary inter-agent scratch files and notes.\n"
    "Do NOT store anything important for the end user in 'artifacts/', as all files inside 'artifacts/' will be automatically deleted/cleaned up. Place permanent user deliverables in main workspace files.\n\n"
    "SKILL ACCESS:\n"
    "All sub-agents have access to 'list_skills' and 'read_skill' to inspect custom skills.\n\n"
    "FOLLOW-UP DELEGATION:\n"
    "If you encounter a task requirement outside your domain (e.g., needing code changes, file moves, or testing), use 'add_subtask_to_master(new_task_description, suggested_agent, reason)' "
    "to pass a suggested follow-up subtask back to the Master Agent!"
)

SUBAGENT_SYSTEM_PROMPTS = {
    "Researcher": (
        "You are the Researcher Sub-Agent — the knowledge discovery, workspace inspection, and documentation expert.\n\n"
        "PRIMARY RESPONSIBILITIES:\n"
        "1. External Knowledge Discovery: Use 'web_search' to find accurate documentation, API specifications, library usage guides, and syntax examples.\n"
        "2. Workspace Inspection: Use 'list_directory_contents' and 'list_all_directory_contents' to survey file trees, find existing modules, and locate resources.\n"
        "3. File & Skill Analysis: Use 'read_file' to inspect source files, and 'list_skills' / 'read_skill' / 'read_create_tool_tutorial' to discover available skills and custom tools.\n"
        "4. Knowledge Synthesis: Compile comprehensive, structured research summaries for the Master Agent.\n\n"
        "OPERATIONAL GUIDELINES & BEHAVIOR:\n"
        "- Never guess or infer implementation details; inspect authoritative source files directly on disk.\n"
        "- Cite exact file paths, line numbers, or external URLs in your research summary.\n"
        "- Check for relevant pre-existing custom tools or skills in the workspace and highlight any that can assist the Master Agent.\n"
        "- Conclude your session cleanly by invoking 'task_complete' with a clear, factual research summary. If critical information is unrecoverable, invoke 'task_failed' with specific reasons."
    ),
    "Coder": (
        "You are the Coder Sub-Agent — the software engineering and code modification specialist.\n\n"
        "PRIMARY RESPONSIBILITIES:\n"
        "1. Source Code Creation: Use 'create_new_file' and 'write_file' to author clean, production-ready code files.\n"
        "2. Code Refactoring & Patching: Use 'file_patch_text' or 'file_add_line' to make precise, targeted modifications to existing codebase files.\n"
        "3. Code Inspection & Standards: Use 'read_file', 'list_skills', and 'read_skill' to inspect existing codebase conventions, design patterns, and skill guidelines.\n\n"
        "OPERATIONAL GUIDELINES & BEHAVIOR:\n"
        "- Write clean, maintainable, modular code following software engineering best practices.\n"
        "- Preserve existing API contracts, docstrings, imports, and error handling logic unless explicitly directed to modify them.\n"
        "- Prefer targeted edits via 'file_patch_text' over completely overwriting large pre-existing files.\n"
        "- Inspect schema definitions, function signatures, and imported symbols using 'read_file' before dereferencing properties.\n"
        "- If code changes require follow-up testing or command execution, use 'add_subtask_to_master' to suggest follow-up verification by the 'Tester and Debugger' or 'System Manager'.\n"
        "- Terminate session gracefully via 'task_complete' with a detailed summary of modified files and functions."
    ),
    "File Manager": (
        "You are the File Manager Sub-Agent — the directory structure, file organization, and workspace hygiene expert.\n\n"
        "PRIMARY RESPONSIBILITIES:\n"
        "1. Directory Operations: Create subdirectories using 'create_directory', survey structures via 'list_directory_contents' and 'list_all_directory_contents'.\n"
        "2. File Lifecycle Management: Re-organize, rename ('rename_item'), move ('move_item'), or safely trash ('trash_item') workspace assets.\n"
        "3. Asset Transfer & Inspection: Deliver files to users via 'send_file_to_user', inspect content via 'read_file', and inspect skills via 'list_skills' / 'read_skill'.\n\n"
        "OPERATIONAL GUIDELINES & BEHAVIOR:\n"
        "- Prioritize workspace safety: verify source and destination paths exist before initiating move, rename, or trash operations.\n"
        "- Maintain standardized directory conventions (e.g., media in 'uploaded_media', agent data in 'agents/', tools in 'custom-tools/').\n"
        "- Never delete or overwrite files blindly without checking file content via 'read_file' first.\n"
        "- When complete, invoke 'task_complete' reporting all moved, renamed, created, or trashed paths."
    ),
    "System Manager": (
        "You are the System Manager Sub-Agent — the execution environment control, service lifecycle, and terminal administrator.\n\n"
        "PRIMARY RESPONSIBILITIES:\n"
        "1. Terminal Execution: Execute system shell commands, package installations, and environment scripts using 'run_command'.\n"
        "2. Service & Process Management: Control server state and hot-reload components via 'restart_mcp_server'.\n"
        "3. Memory State Management: Manage long-term session memory items via 'add_memory' and 'remove_memory'.\n"
        "4. Skill Inspection: Inspect custom environment skills via 'list_skills' and 'read_skill'.\n\n"
        "OPERATIONAL GUIDELINES & BEHAVIOR:\n"
        "- Execute terminal operations safely: review command syntax, working directories, and timeout parameters before calling 'run_command'.\n"
        "- Inspect stdout, stderr, and exit codes. If a command fails, diagnose the exact failure traceback from the log; do NOT ignore exit codes.\n"
        "- Never swallow exceptions or mask errors with silent fallbacks.\n"
        "- Conclude session via 'task_complete' with terminal execution outputs, exit codes, and environment status summaries."
    ),
    "Tester and Debugger": (
        "You are the Tester & Debugger Sub-Agent — the quality assurance, code verification, and root-cause diagnostic expert.\n\n"
        "PRIMARY RESPONSIBILITIES:\n"
        "1. Verification & Testing: Run test suites, linters, and verification scripts via 'run_command'.\n"
        "2. Log & Stack Trace Analysis: Inspect runtime error logs, stack tracebacks, and directory structures ('list_directory_contents', 'list_all_directory_contents', 'read_file').\n"
        "3. Bug Diagnosis: Identify broken contracts, missing imports, syntax errors, or failing assertions.\n\n"
        "OPERATIONAL GUIDELINES & BEHAVIOR:\n"
        "- Base diagnostics strictly on empirical log evidence and error tracebacks. Fetch and read complete un-truncated logs before declaring a root cause.\n"
        "- Never fix errors by masking symptoms, commenting out failing tests, or returning dummy fallbacks.\n"
        "- Verify fixes by re-executing test commands until clean execution is empirically confirmed.\n"
        "- When complete, invoke 'task_complete' providing a structured report containing: (1) Diagnosed Root Cause, (2) Log Evidence, (3) Verification Result."
    )
}


@mcp.tool()
def call_subagent(subagent_name: str, task_instruction: str) -> str:
    """Delegate a task to one of the 5 specific sub-agents defined in structure.md.
    
    Args:
        subagent_name: Must be one of ('Coder', 'File Manager', 'Researcher', 'System Manager', 'Tester and Debugger').
        task_instruction: Specific task description and instructions for the sub-agent to carry out.
    """
    from tool_loader import get_tools_for_agent, load_all_tools
    
    global ALL_LOADED_TOOLS
    if not ALL_LOADED_TOOLS:
        ALL_LOADED_TOOLS = load_all_tools()

    model_name, api_key, api_base = get_subagent_model_info()
    
    try:
        sub_funcs, sub_schemas_chat = get_tools_for_agent(subagent_name, ALL_LOADED_TOOLS)
    except ValueError as ve:
        return f"Error: {ve}"

    # Determine canonical subagent prompt
    # Determine canonical subagent prompt
    norm_prompt_key = subagent_name
    for k in SUBAGENT_SYSTEM_PROMPTS.keys():
        if k.lower().replace(" ", "") == subagent_name.lower().replace(" ", ""):
            norm_prompt_key = k
            break
        if subagent_name.lower() in ["tester", "debugger"] and k == "Tester and Debugger":
            norm_prompt_key = k
            break

    role_prompt = SUBAGENT_SYSTEM_PROMPTS.get(norm_prompt_key, f"You are the {subagent_name} Sub-Agent.")

    # Set active agent name for tool context
    previous_agent = getattr(builtins, "CURRENT_AGENT_NAME", "Master")
    builtins.CURRENT_AGENT_NAME = norm_prompt_key

    # Fetch assigned tasks specifically for this subagent from TASK_QUEUE
    task_context_str = ""
    try:
        from tools.task_management import TASK_QUEUE, _is_task_assigned_to_agent
        assigned_tasks = [t for t in TASK_QUEUE if _is_task_assigned_to_agent(t.get("assigned_agent", ""), norm_prompt_key)]
        if assigned_tasks:
            lines = [f"YOUR ASSIGNED TASKS (from Master Roadmap for {norm_prompt_key}):"]
            for t in assigned_tasks:
                status_symbol = "[x]" if t["status"] == "completed" else ("[/]" if t["status"] == "in_progress" else "[ ]")
                lines.append(f"  {status_symbol} Task #{t['id']}: {t['description']} (Status: {t['status']})")
                if t.get("result_summary"):
                    lines.append(f"      Result: {t['result_summary']}")
            task_context_str = "\n".join(lines) + "\n\n"
    except Exception as e:
        task_context_str = ""

    # Fetch available temporary artifacts filenames from artifacts/ directory
    artifacts_context_str = ""
    try:
        from tools.task_management import get_artifacts_dir
        art_dir = get_artifacts_dir()
        if os.path.exists(art_dir):
            artifact_files = [f"artifacts/{f}" for f in sorted(os.listdir(art_dir)) if os.path.isfile(os.path.join(art_dir, f))]
            if artifact_files:
                art_lines = [f"  - {p}" for p in artifact_files]
                artifacts_context_str = "AVAILABLE SHARED ARTIFACTS (Temporary scratch files in artifacts/):\n" + "\n".join(art_lines) + "\n(Use 'read_file' if you need to inspect the contents of any artifact file above.)\n\n"
    except Exception:
        artifacts_context_str = ""

    print(f"\n==========================================================================")
    print(f"[Master Agent -> Sub-Agent: '{norm_prompt_key}'] Delegating Task")
    print(f"Instructions: {task_instruction}")
    print(f"Available Tools: {list(sub_funcs.keys())}")
    if task_context_str:
        print(f"Loaded Assigned Tasks Context:\n{task_context_str.strip()}")
    if artifacts_context_str:
        print(f"Loaded Shared Artifacts Context:\n{artifacts_context_str.strip()}")
    print(f"==========================================================================")

    sub_system_prompt = (
        f"USER OPERATING SYSTEM: {get_user_os()}\n\n"
        f"{role_prompt}\n\n"
        f"{SUBAGENT_DIRECTORY_INFO}\n\n"
        f"SESSION ISOLATION & MEMORY:\n"
        f"You are running in a dedicated mini-session for this specific task.\n"
        f"Working Directory: 'master/working'\n"
        f"Task Instruction: {task_instruction}\n\n"
        f"{task_context_str}"
        f"{artifacts_context_str}"
        f"All tool calls and results are remembered in this mini-session context.\n"
        f"When complete, call 'task_complete' with your result summary, or 'task_failed' if blocked."
    )

    messages = [
        {"role": "system", "content": sub_system_prompt},
        {"role": "user", "content": task_instruction}
    ]

    max_steps = 15
    step_count = 0
    final_output = ""

    try:
        while step_count < max_steps:
            step_count += 1

        api_params = {
            "model": model_name,
            "messages": messages,
        }
        if sub_schemas_chat:
            api_params["tools"] = sub_schemas_chat
            api_params["tool_choice"] = "auto"
        if api_key:
            api_params["api_key"] = api_key
        if api_base:
            api_params["api_base"] = api_base

        is_non_reasoning_model = (
            "gpt-4" in model_name or
            "gpt-3" in model_name or
            "davinci" in model_name or
            "gemini" in model_name or
            "claude" in model_name or
            "groq" in model_name or
            "ollama" in model_name
        )
        if not is_non_reasoning_model:
            api_params["max_completion_tokens"] = 4000
            api_params["reasoning_effort"] = "medium"
        else:
            api_params["max_tokens"] = 4000

        try:
            response = litellm.completion(**api_params)
        except Exception as api_err:
            err_str = str(api_err).lower()
            if "reasoning_effort" in err_str or "max_completion_tokens" in err_str or "unsupported parameter" in err_str or "extra parameters" in err_str or "unexpected keyword" in err_str:
                api_params.pop("reasoning_effort", None)
                if "max_completion_tokens" in err_str or "max_completion_tokens" not in api_params:
                    api_params.pop("max_completion_tokens", None)
                    api_params["max_tokens"] = 4000
                try:
                    response = litellm.completion(**api_params)
                except Exception as fall_err:
                    return f"Error during sub-agent '{subagent_name}' execution: {fall_err}"
            else:
                return f"Error during sub-agent '{subagent_name}' execution: {api_err}"

        msg = response.choices[0].message

        if msg.tool_calls:
            tool_calls_list = []
            for tc in msg.tool_calls:
                fn_args_str = tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments)
                tool_calls_list.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": fn_args_str
                    }
                })

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": tool_calls_list
            })

            task_finished = False
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except Exception:
                    args = {}

                print(f"  [Sub-Agent: {subagent_name}] Tool Call: '{fn_name}'")
                print(f"  [Sub-Agent: {subagent_name}] Arguments: {json.dumps(args)}")

                if UI_CALLBACK:
                    try:
                        UI_CALLBACK("system", f"[Master Subagent -> {subagent_name}] Tool Call: `{fn_name}`\n`{json.dumps(args)}`")
                    except Exception:
                        pass

                if fn_name in sub_funcs:
                    try:
                        res = sub_funcs[fn_name](**args)
                    except Exception as err:
                        res = f"Error executing '{fn_name}': {err}"
                else:
                    res = f"Error: Tool '{fn_name}' not available for sub-agent '{subagent_name}'."

                print(f"  [Sub-Agent: {subagent_name}] Result: {str(res)[:250]}{'...' if len(str(res)) > 250 else ''}")

                if UI_CALLBACK:
                    try:
                        UI_CALLBACK("system", f"[Master Subagent -> {subagent_name}] Tool Result (`{fn_name}`):\n```{str(res)[:300]}```")
                    except Exception:
                        pass

                messages.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": str(res)
                })

                if fn_name in ["task_complete", "task_failed"]:
                    final_output = f"Sub-Agent '{subagent_name}' finished: {res}"
                    task_finished = True

            if task_finished:
                print(f"[Sub-Agent: '{subagent_name}'] Session Finished.\n")
                return final_output

            continue
        else:
            text = msg.content or ""
            messages.append({"role": "assistant", "content": text})
            if text:
                final_output = text
                print(f"[Sub-Agent: '{subagent_name}'] Response: {final_output}\n")
            break

        return final_output or f"Sub-Agent '{subagent_name}' finished task execution."
    finally:
        builtins.CURRENT_AGENT_NAME = previous_agent