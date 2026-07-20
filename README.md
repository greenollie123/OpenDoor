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

## ✨ Key Features

- **Multi-Agent Flask Coordinator (`main.py`)**: A centralized coordinator acting as a message/event router between custom agents and external frontends (Terminal, TUI, WhatsApp, Web).
- **FastMCP Integration (`mcp_server.py`)**: Seamlessly implements the Model Context Protocol (MCP) to dynamically publish core system and custom tools.
- **Hot-Reloading Tool Loader**: Automatically scans and updates active tools from the `tools/` and `master/working/custom-tools/` directories without restarting the coordinator.
- **Interactive Consent & Approvals**: Features a secure consent flow (`ask_for_consent` tool) requiring manual user approval via API before agents run sensitive operations.
- **Persistent Memory & Expiry**: An agent-specific persistent JSON memory structure enabling agents to store, update, retrieve, and auto-expire facts/preferences.
- **Multiple Interface Frontends**:
  - **Terminal TUI**: A terminal UI built with Textual for fluid agent conversations and autocompletion.
  - **CLI Terminal Shell**: Run direct command prompts (`opendoor ask`) or interactive CLI chat sessions.
  - **WhatsApp Bot Gateway**: Neonize-powered WhatsApp gateway to chat with agents directly on your phone.
  - **React Web UI**: A Vite + React dashboard to inspect logs, customize agents, toggle tools, and manage skills.
- **Developer-First Bootstrap**: Auto-copies example configuration templates and pauses setup, guiding you through setting up API keys, latitude/longitude, and default models.

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
- **Terminal Client (`terminal/terminal.py`)**: An interactive chat shell and command-line utility for chatting with agents directly from the command prompt.
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
├── terminal/                  # Terminal Client & Shortcuts
│   ├── terminal.py            # Terminal Client Core
└── sub-programs/
    ├── TUI/                   # Textual Terminal UI
    │   └── TUI.py
    ├── whatsapp/              # WhatsApp Neonize bridge
    │   └── whatsapp.py
    └── web-ui/                # Vite React dashboard
```

---

## 🛠️ Setup Instructions

### 1. Prerequisites

- **Python 3.10 to 3.12**
- **Node.js 18+** (for the Web UI)
- **Operating system**: Windows 10/11, macOS, or Linux.

### 2. Setup

Run the setup script for your platform in the project root folder. This script automatically creates the Python virtual environment, installs all dependencies, configures the terminal command `opendoor` to be globally accessible, and launches the interactive configuration wizard.

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

### 3. Interactive Configuration Wizard:
At the end of the platform setup script, the interactive wizard will launch in the same terminal window. You can also re-run it at any time using:
```bash
opendoor setup
```

In the configuration wizard, you can:
- Configure default AI models and location.
- Check download status, install, or update sub-programs (`web-ui`, `whatsapp`, `TUI`).
- Automatically install dependencies and build the `web-ui` (`npm install` & `npm run build`) upon download.

*Note: After running the initial setup, please restart your terminal to apply the PATH changes.*

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
