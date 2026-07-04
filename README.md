# OpenDoor

OpenDoor is a modular, multi-agent AI assistant ecosystem designed to run locally on your desktop. It integrates a central **Flask API coordinator**, a **FastMCP Server** for dynamic tool execution, and multiple specialized **subprograms** for interacting with the AI via terminal, web, voice, or WhatsApp.

---

## 📸 Overview of the Ecosystem

```
             ┌────────────────────────┐
             │       main.py          │
             │   (Flask Webhook API)  │
             └───────────┬────────────┘
                         │
         ┌───────────────┼───────────────┬───────────────┐
         ▼               ▼               ▼               ▼
┌────────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
│     TUI.py     ││  whatsapp.py ││voice-detector││    Web UI    │
│ (Textual TUI)  ││ (Neonize bot)││    (SOON)    ││(Vite React)  │
└────────────────┘└──────────────┘└──────────────┘└──────────────┘
```

- **Core Coordinator (`main.py`)**: Launches the Flask webhooks server on `http://127.0.0.1:5050` and acts as the central router for messages and UI updates across all channels.
- **FastMCP Server (`mcp_server.py`)**: Dynamically loads tools (from `tools/` and `master/working/custom-tools/`) and connects them via the Model Context Protocol (MCP).
- **Textual TUI (`sub-programs/TUI/TUI.py`)**: A modern terminal interface for text chatting with auto-completion and agent selection.
- **WhatsApp Gateway (`sub-programs/whatsapp/whatsapp.py`)**: Leverages `neonize` to connect the AI as a chatbot responder to your WhatsApp number.
- **Web UI (`sub-programs/web-ui/`)**: A sleek React dashboard built with Vite to manage agents, view chat logs, and toggle tools.

---

## 📂 Project Structure

The only files strictly required to use this are `main.py`, `mcp_server.py` and `config.yaml.example`.

```text
├── main.py                    # Coordinator and main entrypoint
├── mcp_server.py              # MCP tool loading server
├── config.yaml.example        # Core configuration template
├── requirements.txt           # Python package dependencies
├── LICENSE                    # MIT License
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
- **System Audio Drivers**: 
  - *Windows*: Ensure you have your microphone and speaker devices enabled.
  - *Linux/macOS* (UNTESTED): Install `portaudio` before installing Python dependencies.
    - Debian/Ubuntu: `sudo apt-get install portaudio19-dev`
    - macOS (Homebrew): `brew install portaudio`

### 2. Dependency Setup

In your project root, install the dependencies for Python and the Web UI:

```bash
# Python Virtual Environment & Requirements
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt

# Web UI Packages
cd sub-programs/web-ui
npm install
cd ../..
```

---

## 🚀 Running the Assistant

Simply activate your virtual environment and run the main coordinator:

```bash
python main.py
```

This will automatically create a `Terry` agent.

### ⚙️ Automatic Configuration Bootstrap
You **do not** need to copy configuration files manually. 
* On first startup, `main.py` will automatically detect if `config.yaml` is missing, copy it from `config.yaml.example`, and pause execution.
* Simply edit your `config.yaml` in your editor, save it, and press **ENTER** in your terminal window to resume boot.
* The same automatic copy and pause-to-edit flow happens for `whatsapp_config.yaml` when the WhatsApp subprogram launches.

