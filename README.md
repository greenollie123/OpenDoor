# OpenDoor

OpenDoor is a modular, multi-agent AI assistant ecosystem designed to run locally on your desktop. It integrates a central **Flask API coordinator**, a **FastMCP Server** for dynamic tool execution, a specialized **Master Sub-Agent Engine** for multi-agent task planning and execution, and multiple frontends for interacting with your AI (Terminal, Textual TUI, WhatsApp, and Web).

<p align="center">
  <a href="https://github.com/greenollie/OpenDoor/commits/main/">
    <img src="https://img.shields.io/github/commit-activity/t/greenollie/OpenDoor?label=TOTAL%20COMMITS&color=blue&style=for-the-badge" alt="Total Commits" />
  </a>
&nbsp;&nbsp;
  <a href="https://github.com/greenollie/OpenDoor/commits/main/">
    <img src="https://img.shields.io/github/last-commit/greenollie/OpenDoor?style=for-the-badge&color=red" alt="Last Commit" />
  </a>
</p>

---

## ✨ Key Features

- **Multi-Agent Flask Coordinator (`main.py`)**: A centralized coordinator acting as a message and event router between custom agents, sub-agents, and external frontends.
- **Master Sub-Agent Architecture (`master-sub-agent/`)**: Autonomous task decomposition engine that creates high-level roadmaps and delegates subtasks to partitioned, domain-specific sub-agents (**Coder**, **File Manager**, **Researcher**, **System Manager**, **Tester & Debugger**).
- **FastMCP Integration (`mcp_server.py`)**: Implements the Model Context Protocol (MCP) to dynamically publish core system and custom tools.
- **Granular Modular Tooling (`tools/`)**: Isolated, single-purpose tool modules covering file operations, Excel file manipulation, system command execution, memory management, skills, search, and user notifications.
- **LiteLLM & Universal Model Support (`models.yaml`)**: Provider-agnostic AI model routing powered by LiteLLM. Easily configure main models, sub-agent models, embeddings, STT, and TTS across OpenAI, Claude, Gemini, Ollama, OpenRouter, and custom endpoints.
- **Multi-Channel Registry (`channels.yaml`)**: Configurable channel handling for WhatsApp, Voice, Textual TUI, CLI Terminal, and Web UI interfaces.
- **Interactive Consent & Security**: Secure consent flow (`ask_for_consent` tool) requiring manual user approval before running sensitive or destructive operations.
- **Persistent Memory & Expiry**: Agent-specific persistent memory structure enabling agents to store, update, retrieve, and auto-expire facts and user preferences.
- **Multiple Frontends**:
  - **Terminal TUI**: A modern terminal interface built with Textual for fluid agent conversations and autocompletion.
  - **CLI Terminal Shell**: Run direct command prompts (`opendoor ask`) or interactive CLI chat sessions (`opendoor chat`).
  - **WhatsApp Bot Gateway**: Neonize-powered WhatsApp gateway to chat with your agents directly on your phone.
  - **React Web UI**: A Vite + React dashboard to inspect logs, customize agents, toggle tools, and manage skills.
- **Developer-First Bootstrap**: Automated setup scripts (`setup-windows.bat`, `setup-linux-macos.sh`) and interactive CLI wizard (`opendoor setup`) to configure models, API keys, location, and sub-programs.

---

## 📸 Ecosystem Architecture

```text
                           ┌────────────────────────┐
                           │       main.py          │
                           │   (Flask Webhook API)  │
                           └───────────┬────────────┘
                                       │
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        ▼               ▼               ▼               ▼               ▼
 ┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
 │    TUI.py    ││ terminal.py  ││ whatsapp.py  ││ voice (TTS)  ││    Web UI    │
 │   (Textual)  ││    (CLI)     ││  (Neonize)   ││   Detector   ││ (Vite React) │
 └──────────────┘└──────────────┘└──────────────┘└──────────────┘└──────────────┘
                                       │
                                       ▼
                           ┌────────────────────────┐
                           │   master-sub-agent/    │
                           │ (Task Planner Engine)  │
                           └───────────┬────────────┘
                                       │
         ┌───────────────┬─────────────┼─────────────┬───────────────┐
         ▼               ▼             ▼             ▼               ▼
   ┌───────────┐   ┌───────────┐ ┌───────────┐ ┌───────────┐   ┌───────────┐
   │   Coder   │   │File Mngr  │ │Researcher │ │Sys Manager│   │  Tester   │
   └───────────┘   └───────────┘ └───────────┘ └───────────┘   └───────────┘
```

---

## 📂 Project Structure

```text
├── main.py                    # Flask coordinator and webhook router
├── mcp_server.py              # FastMCP tool loader server
├── config.yaml.example        # Core system configuration template
├── models.yaml                # LiteLLM model provider configuration
├── channels.yaml              # Multi-channel interface definitions
├── requirements.txt           # Python package dependencies
├── setup-windows.bat          # Automated Windows setup script
├── setup-linux-macos.sh       # Automated macOS/Linux setup script
├── master-sub-agent/          # Master Sub-Agent orchestration engine
├── tools/                     # Core system tools
├── terminal/                  # CLI & Terminal Tools
└── sub-programs/              # External interface sub-programs
    ├── TUI/                   # Textual Terminal UI
    ├── whatsapp/              # WhatsApp Neonize bridge
    └── web-ui/                # Vite + React dashboard web server
```

---

## 🤖 Master Sub-Agent Roles

The Master Sub-Agent system dynamically delegates complex user prompts across five specialized roles to avoid context rot and tool overlap:

| Sub-Agent Role | Primary Focus & Tool Access |
| :--- | :--- |
| **Coder** | Code writing, file patching, refactoring (`read_file`, `write_file`, `file_patch_text`, `file_add_line`, `create_new_file`) |
| **File Manager** | Directory navigation, file organization (`list_directory_contents`, `create_directory`, `move_item`, `trash_item`, `send_file_to_user`) |
| **Researcher** | Information gathering and web lookup (`web_search`, `read_skill`, `read_create_tool_tutorial`) |
| **System Manager** | Execution environment, service lifecycle, memory updates (`run_command`, `restart_mcp_server`, `add_memory`, `remove_memory`) |
| **Tester & Debugger** | Runtime verification, testing, log analysis (`read_file`, `run_command`) |

---

## 🛠️ Setup & Installation

### 1. Prerequisites

- **Python 3.10 to 3.12**
- **Node.js 18+** (required for Web UI)
- **Operating System**: Windows 10/11, macOS, or Linux

### 2. Quick Setup

Run the setup script for your operating system from the project root folder. This script automatically sets up the Python virtual environment, installs dependencies, registers the `opendoor` CLI command globally, and launches the interactive configuration wizard.

#### Windows
Double-click `setup-windows.bat` or run in Command Prompt / PowerShell:
```cmd
setup-windows.bat
```

#### macOS / Linux
Run in your terminal:
```bash
chmod +x setup-linux-macos.sh
./setup-linux-macos.sh
```

### 3. Interactive Configuration Wizard

At the end of setup, the interactive configuration wizard will launch. You can re-run it at any time using:
```bash
opendoor setup
```

Through the wizard, you can:
- Select and configure AI model providers (OpenAI, Claude, Gemini, Ollama, OpenRouter, LiteLLM).
- Manage API keys and default parameters.
- Install, update, or build sub-programs (`web-ui`, `whatsapp`, `TUI`).

*Note: Restart your terminal after initial setup to apply global PATH updates.*

---

## 🚀 Running OpenDoor

Once setup is complete, control your OpenDoor server and clients using the global `opendoor` CLI:

### 1. Server Control Commands

```bash
opendoor launch    # Start the coordinator server & background services
opendoor stop      # Stop all active server processes and subprograms
opendoor restart   # Restart the coordinator server and active subprograms
opendoor update    # Check for repository updates and upgrade dependencies
```

Starting the server launches the Flask coordinator on `http://127.0.0.1:5050` and automatically starts configured subprograms (TUI, WhatsApp, Web UI).

### 2. Interacting with Agents

- **Interactive CLI Chat Session**:
  ```bash
  opendoor chat
  ```
- **Single Command Query**:
  ```bash
  opendoor ask "What is the status of my project tasks?"
  opendoor ask Terry "What is the weather today?"
  ```

