import os
import sys
import json
import platform
import yaml
import litellm
from tool_loader import load_all_tools, get_tools_for_agent, set_active_workspace
import tools.call_subagent as call_sub_mod

def get_user_os() -> str:
    override = os.environ.get("USER_OS")
    if override:
        return override
    return f"{platform.system()} {platform.release()} ({platform.machine()})"

def get_subagent_model_info():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
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

def run_master_subagent(task_instruction: str, agent_name: str = "Terry", ui_callback=None) -> str:
    """Run the Master Subagent programmatically, scoped strictly to 'master/working'."""
    # 1. Scope workspace strictly to master/working
    scoped_workspace = set_active_workspace(agent_name)
    import builtins
    builtins.CURRENT_AGENT_NAME = agent_name
    
    # 2. Register UI callback and workspace in subagent runner
    if ui_callback:
        call_sub_mod.UI_CALLBACK = ui_callback
    
    model_name, api_key, api_base = get_subagent_model_info()

    # Load system tools
    all_functions = load_all_tools()
    call_sub_mod.ALL_LOADED_TOOLS = all_functions

    # Master Agent tools ONLY
    master_functions, master_schemas_chat = get_tools_for_agent("Master", all_functions)

    master_system_prompt = (
        f"USER OPERATING SYSTEM: {get_user_os()}\n\n"
        f"You are the Master Agent operating under the Multi-Agent System Architecture defined in structure.md.\n"
        f"You are operating on behalf of main agent: '{agent_name}'.\n"
        f"Your working directory is set to the full workspace: 'master/working'.\n\n"
        "CORE RESTRICTIONS & TOOLSETS:\n"
        "1. RESTRICTED TOOLSET: You DO NOT have direct access to code editing, web search, command execution, or directory tools.\n"
        "   Your tools are strictly limited to:\n"
        "   - 'create_todo_list' and 'update_task_status' (high-level roadmap management)\n"
        "   - 'read_file' and 'write_file' (planning and document reading/writing inside the working directory)\n"
        "   - 'call_subagent' (delegating tasks to specialized sub-agents)\n\n"
        "2. ALLOWED SUB-AGENTS (structure.md):\n"
        "   You can ONLY delegate work to these 5 sub-agents:\n"
        "   - 'Researcher': Web searches, documentation research, skill tutorials, listing directory contents. (CALL FIRST!)\n"
        "   - 'Coder': Writing, editing, patching codebase files inside the workspace directory.\n"
        "   - 'File Manager': Managing directory structure, file moving/renaming/trashing inside the workspace directory.\n"
        "   - 'System Manager': Command execution, service control, memory management.\n"
        "   - 'Tester and Debugger': Testing execution, inspecting command outputs and logs.\n\n"
        "3. MANDATORY 3-PHASE WORKFLOW RULES:\n"
        "   - PHASE 1 (RESEARCH): Call the 'Researcher' sub-agent first to gather information, inspect directory contents, or perform web/documentation research.\n"
        "   - PHASE 2 (IMPLEMENTATION PLAN): BEFORE calling any execution agent (Coder, File Manager, System Manager, Tester and Debugger), "
        "     you MUST create and finish a detailed implementation plan file located specifically in the shared artifacts directory: "
        "     'artifacts/implementation_plan.md' using 'write_file'. The implementation plan must outline "
        "     all proposed changes, tasks, sub-agents to use, and verification steps. DO NOT invoke Coder, File Manager, System Manager, "
        "     or Tester and Debugger until 'artifacts/implementation_plan.md' is finished!\n"
        "   - PHASE 3 (EXECUTION & UPDATES): Call the appropriate execution sub-agents to perform the planned tasks. Update "
        "     'artifacts/implementation_plan.md' and 'update_task_status' throughout progress as tasks are completed or updated.\n\n"
        "4. SHARED TEMPORARY ARTIFACTS RULE:\n"
        "   The 'artifacts/' directory is strictly for temporary inter-agent scratch files and notes. Do NOT store anything important for the end user in 'artifacts/', "
        "   as all files inside 'artifacts/' will be automatically deleted/cleaned up when new tasks are created or cleanup is run. Place all permanent user deliverables in main workspace files."
    )

    if ui_callback:
        ui_callback("system", f"[Master Subagent Started] Task for agent `{agent_name}`:\n> {task_instruction}")

    messages = [
        {"role": "system", "content": master_system_prompt},
        {"role": "user", "content": task_instruction}
    ]
    max_steps = 25
    step_count = 0
    final_summary = ""

    while step_count < max_steps:
        step_count += 1
        
        api_params = {
            "model": model_name,
            "messages": messages,
        }
        if master_schemas_chat:
            api_params["tools"] = master_schemas_chat
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
                    err = f"LiteLLM API Error: {fall_err}"
                    if ui_callback:
                        ui_callback("system", f"[Error] {err}")
                    return err
            else:
                err = f"LiteLLM API Error: {api_err}"
                if ui_callback:
                    ui_callback("system", f"[Error] {err}")
                return err

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

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except Exception:
                    args = {}

                if ui_callback:
                    ui_callback("system", f"[Master Subagent] Executing Master Tool: `{fn_name}`\n`{json.dumps(args)}`")

                if fn_name in master_functions:
                    try:
                        res = master_functions[fn_name](**args)
                    except Exception as err:
                        res = f"Error executing '{fn_name}': {err}"
                else:
                    res = f"Error: Tool '{fn_name}' not available for Master Agent."

                if ui_callback:
                    ui_callback("system", f"[Master Subagent] Tool Result (`{fn_name}`):\n```{str(res)[:300]}```")

                messages.append({
                    "tool_call_id": tc.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": str(res)
                })

            continue
        else:
            text = msg.content or ""
            messages.append({"role": "assistant", "content": text})
            if text:
                final_summary = text
                if ui_callback:
                    ui_callback("assistant", f"[Master Subagent Final Response]\n{final_summary}")
            break

    result_text = final_summary or f"Master Subagent finished execution for agent '{agent_name}'."
    if ui_callback:
        ui_callback("system", f"[Master Subagent Finished] Execution complete for agent `{agent_name}`.")
    return result_text
