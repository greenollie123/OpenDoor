# Multi-Agent System Architecture Specification

## 1. System Flow Overview

```text
               ┌───────────────────────┐
               │         Agent         │
               └───────────┬───────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │ Master Agent Planning │
               │  - Implementation Plan│
               │  - Create Todo List   │
               │  - Pick First Agent   │
               └───────────┬───────────┘
                           │
      ┌────────────────────┼────────────────────┬────────────────────┬────────────────────┐
      │                    │                    │                    │                    │
      ▼                    ▼                    ▼                    ▼                    ▼
┌───────────┐        ┌───────────┐        ┌───────────┐        ┌───────────┐        ┌───────────┐
│   Coder   │        │ File      │        │ Researcher│        │ System    │        │ Tester &  │
│           │        │ Manager   │        │           │        │ Manager   │        │ Debugger  │
└─────┬─────┘        └─────┬─────┘        └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
      │                    │                    │                    │                    │
      └────────────────────┴────────────────────┼────────────────────┴────────────────────┘
                                                │
                                                ▼
                               ┌────────────────────────────────┐
                               │     Sub-Agent Tools & State    │
                               └────────────────────────────────┘

```

---

## 2. Orchestration & Master Agent Tools

The Master Agent handles high-level roadmap creation, task delegation, and progress tracking using these shared state management tools:

* `create_todo_list(tasks: list[str])`: Initializes the high-level roadmap for the incoming user request.
* `update_task_status(task_id: int, status: "pending" | "in_progress" | "completed")`: Tracks global implementation progress.

---

## 3. Sub-Agent Definitions & Tool Distribution

To prevent context rot and tool interference, tools are tightly partitioned across five specialized sub-agents:

### A. Coder

*Focus: Writing, editing, and modifying codebase files.*

* `read_file`
* `write_file`
* `file_patch_text`
* `file_add_line`
* `create_new_file`
* `list_skills`
* `read_skill`

### B. File Manager

*Focus: Managing directory structure, file moving, and file transfer.*

* `list_directory_contents`
* `list_all_directory_contents`
* `create_directory`
* `rename_item`
* `move_item`
* `read_file`
* `trash_item`
* `send_file_to_user`
* `list_skills`
* `read_skill`

### C. Researcher

*Focus: Searching external knowledge, documentation, and system tutorials. Checks for useful tools and passes any that may be helpful to the Master Agent.*

* `web_search`
* `list_skills`
* `read_skill`
* `read_create_tool_tutorial`
* `read_file`

### D. System Manager

*Focus: Controlling execution environment, service states, and memory.*

* `run_command`
* `restart_mcp_server`
* `add_memory`
* `remove_memory`
* `list_skills`
* `read_skill`

### E. Tester and Debugger

*Focus: Code execution verification and error inspection.*

* `read_file`
* `run_command`
* `list_skills`
* `read_skill`

---

## 4. Shared Sub-Agent Execution Utilities

Every sub-agent is initialized with the following control utilities to manage tasks and communicate results back up to the Master Agent:

* `read_my_tasks()`: Lets the sub-agent check its active assignments and contextual goals.
* `add_subtask_to_master(new_task_description: str, suggested_agent: str, reason: str)`: Pass-back mechanism. Allows a sub-agent (e.g., `Tester`) to inject a new follow-up task directly into the Master Agent's queue upon encountering bugs or new requirements.
* `mark_task_complete(task_id: int, result_summary: str)`: Signals completion and returns a clean, compact summary back to the Master Agent.
* `task_complete(summary)`: Gracefully terminates the sub-agent session and passes the final summary back to the Master Agent.
* `task_failed(reason, logs)`: Allows a sub-agent to report an error or unresolvable blocker without getting stuck in a retrying loop.