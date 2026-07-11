# OpenDoor

OpenDoor is a modular, multi-agent AI assistant ecosystem designed to run locally on your desktop. It integrates a central **Flask API coordinator**, a **FastMCP Server** for dynamic tool execution, and multiple specialized **subprograms** for interacting with the AI via terminal, web, or WhatsApp.

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

## 📸 Overview of the Ecosystem

```
                           ┌────────────────────────┐
                           │       main.py          │
                           │   (Flask Webhook API)  │
                           └───────────┬────────────┘
                                       │
       ┌───────────────┬───────────────┼───────────────┬───────────────┐
       ▼               ▼               ▼               ▼               ▼
┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
│    TUI.py    ││ terminal.py  ││ whatsapp.py  ││voice-detector││    Web UI    │
│   (Textual)  ││              ││  (Neonize)   ││    (SOON)    ││ (Vite React) │
└──────────────┘└──────────────┘└──────────────┘└──────────────┘└──────────────┘
```

- **Core Coordinator (`main.py`)**: Launches the Flask webhooks server on `http://127.0.0.1:5050` and acts as the central router for messages and UI updates across all channels.
- **FastMCP Server (`mcp_server.py`)**: Dynamically loads tools (from `tools/` and `master/working/custom-tools/`) and connects them via the Model Context Protocol (MCP).
- **Textual TUI (`sub-programs/TUI/TUI.py`)**: A modern terminal interface for text chatting with auto-completion and agent selection.
- **Terminal Client (`sub-programs/terminal/terminal.py`)**: An interactive chat shell and command-line utility for chatting with agents directly from the command prompt.
- **WhatsApp Gateway (`sub-programs/whatsapp/whatsapp.py`)**: Leverages `neonize` to connect the AI as a chatbot responder to your WhatsApp number.
- **Web UI (`sub-programs/web-ui/`)**: A sleek React dashboard built with Vite to manage agents, view chat logs, and toggle tools.

---

## 📂 Project Structure

The only files strictly required to start this are `main.py`, `mcp_server.py` and `config.yaml.example`.

```text
├── main.py                    # Coordinator and main entrypoint
├── mcp_server.py              # MCP tool loading server
├── config.yaml.example        # Core configuration template
├── requirements.txt           # Python package dependencies
├── LICENSE                    # License stuff
├── setup-windows.bat          # Automated Windows setup and PATH config
├── setup-linux-macos.sh       # Automated macOS/Linux setup and PATH config
├── master/working/skills/     # Useful pre-made skills
├── tools/                     # Core system tools (Weather, Memory, Files, etc.)
│   ├── directory.py
│   ├── file_management.py
│   ├── file_operations.py
│   ├── memory.py
│   ├── move_item.py
│   ├── skills.py
│   └── weather.py
└── sub-programs/
    ├── TUI/                   # Textual Terminal UI
    │   └── TUI.py
    ├── terminal/              # Terminal Client & Shortcuts
    │   ├── terminal.py        # Terminal Client Core
    ├── whatsapp/              # WhatsApp Neonize bridge
    │   └── whatsapp.py
    └── web-ui/                # Vite React dashboard
```

---

## 🛠️ Setup Instructions

### 1. Prerequisites

- **Python 3.10 to 3.12**
- **Node.js 18+** (for the Web UI)
- **OpenAI API Key** (set as environment variable `OPENAI_API_KEY`)
- **Operating system**: Windows 10/11, macOS, or Linux.

### 2. Setup

Run the setup script for your platform in the project root folder. This script automatically creates the Python virtual environment, installs all pip dependencies, and adds the OpenDoor directory to your user PATH so you can run the commands from anywhere:

#### Windows:
Double-click `setup-windows.bat` or run in your Command Prompt/PowerShell:
```cmd
setup-windows.bat
```

#### macOS / Linux:
Run in your terminal:
```bash
chmod +x setup-linux-macos.sh
./setup-linux-macos.sh
```

*Note: After running the setup script, please restart your terminal to apply the PATH changes.*

#### Startup:
Start OpenDoor and prepare for first startup.
Run this in your terminal:
```cmd
opendoor launch --terminal
```
*`--terminal` is used to allow for connecting to whatsapp and checking configs.*

---

## 🚀 Running the Assistant

Once setup is complete, you can start the coordinator server and CLI terminal client from anywhere:

### 1. Start the Server
Run any of the following alias commands:
```bash
opendoor launch
```
This launches the multi-agent Flask coordinator on `http://127.0.0.1:5050` and automatically boots up the subprograms (TUI, Terminal, WhatsApp, Web UI) in separate terminal/console windows depending on what is available.

### 2. Run the Terminal Client
You can chat with your agents interactively in the terminal by running:
```bash
opendoor chat
```

Or execute one-off commands from your shell:
```bash
opendoor ask Terry "what is the weather today?"
```

### ⚙️ Automatic Configuration Bootstrap
You **do not** need to copy configuration files manually. 
* On first startup, the server will automatically detect if `config.yaml` is missing, copy it from `config.yaml.example`, and pause execution.
* Simply edit your `config.yaml` in your editor, save it, and press **ENTER** in your server terminal window to resume boot.
* The same automatic copy and pause-to-edit flow happens for `whatsapp_config.yaml` when the WhatsApp subprogram launches.


