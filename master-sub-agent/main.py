import os
import sys
import json
import platform
import yaml
import litellm
from tool_loader import load_all_tools, get_tools_for_agent, AI_WORKSPACE_DIR
import tools.call_subagent as call_sub_mod

def get_multiline_input():
    print("\nYou: (Type/paste multi-line message below. Press Enter twice or type 'SEND' to submit)")
    print("-" * 60)
    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            if lines:
                break
            else:
                return None
        if line.strip().upper() == "SEND":
            break
        if not line and lines and not lines[-1]:
            # Double enter (two blank lines in a row) -> submit
            lines.pop()
            break
        lines.append(line)
    print("-" * 60)
    return "\n".join(lines).strip()

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

def main():
    model_name, api_key, api_base = get_subagent_model_info()

    # Load all system tools
    all_functions = load_all_tools()

    # Register global tool pool for sub-agent invocation
    call_sub_mod.ALL_LOADED_TOOLS = all_functions

    # Master Agent ONLY gets Master tools (create_todo_list, update_task_status, read_file, write_file, call_subagent)
    master_functions, master_schemas_chat = get_tools_for_agent("Master", all_functions)

    master_system_prompt = (
        f"USER OPERATING SYSTEM: {get_user_os()}\n\n"
        "You are the Master Agent operating under the Multi-Agent System Architecture defined in structure.md.\n"
        "Your working directory is set to 'master/working'.\n\n"
        "CORE RESTRICTIONS & TOOLSETS:\n"
        "1. RESTRICTED TOOLSET: You DO NOT have direct access to code editing, web search, command execution, or directory tools.\n"
        "   Your tools are strictly limited to:\n"
        "   - 'create_todo_list' and 'update_task_status' (high-level roadmap management)\n"
        "   - 'read_file' and 'write_file' (planning and document reading/writing)\n"
        "   - 'call_subagent' (delegating tasks to specialized sub-agents)\n\n"
        "2. ALLOWED SUB-AGENTS (structure.md):\n"
        "   You can ONLY delegate work to these 5 sub-agents:\n"
        "   - 'Researcher': Web searches, documentation research, skill tutorials, listing directory contents. Checks for useful tools and passes any that may be helpful to the main agent. (CALL FIRST!)\n"
        "   - 'Coder': Writing, editing, patching codebase files.\n"
        "   - 'File Manager': Managing directory structure, file moving/renaming/trashing.\n"
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

    print("==========================================================================")
    print(f"Master Agent (LiteLLM - Sub-Agent Orchestrator using '{model_name}')")
    print("Architecture: structure.md | Mode: Master Agent Orchestration")
    print(f"Workspace Path: {AI_WORKSPACE_DIR}")
    print(f"Master Tools: {list(master_functions.keys())}")
    print("Allowed Sub-Agents: ['Coder', 'File Manager', 'Researcher', 'System Manager', 'Tester and Debugger']")
    print("==========================================================================")
    print("Type 'exit' or 'quit' to end the session.\n")

    messages = [{"role": "system", "content": master_system_prompt}]

    while True:
        user_input = get_multiline_input()
        if user_input is None:
            print("\nExiting session. Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ['exit', 'quit']:
            print("Session ended. Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # Master Agent reasoning & delegation loop
        while True:
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
            except Exception as e:
                err_str = str(e).lower()
                if "reasoning_effort" in err_str or "max_completion_tokens" in err_str or "unsupported parameter" in err_str or "extra parameters" in err_str or "unexpected keyword" in err_str:
                    api_params.pop("reasoning_effort", None)
                    if "max_completion_tokens" in err_str or "max_completion_tokens" not in api_params:
                        api_params.pop("max_completion_tokens", None)
                        api_params["max_tokens"] = 4000
                    try:
                        response = litellm.completion(**api_params)
                    except Exception as fall_err:
                        print(f"\n[LiteLLM API Error] {fall_err}")
                        break
                else:
                    print(f"\n[LiteLLM API Error] {e}")
                    break

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

                    print(f"\n[Master Tool Call] Running tool: '{fn_name}'")
                    print(f"[Master Tool Args] {json.dumps(args, indent=2)}")

                    if fn_name in master_functions:
                        try:
                            result = master_functions[fn_name](**args)
                        except Exception as err:
                            result = f"Error executing Master tool '{fn_name}': {err}"
                    else:
                        result = f"Error: Tool '{fn_name}' is not allowed for Master Agent."

                    print(f"[Master Tool Result] {str(result)[:300]}{'...' if len(str(result)) > 300 else ''}")

                    messages.append({
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "name": fn_name,
                        "content": str(result)
                    })

                continue
            else:
                text = msg.content or ""
                messages.append({"role": "assistant", "content": text})
                if text:
                    print(f"\nAgent: {text}")
                break

if __name__ == "__main__":
    main()