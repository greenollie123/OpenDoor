#!/usr/bin/env bash

# Exit on error
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Project directory: $DIR"

# 1. Create virtual environment if it doesn't exist
if [ ! -d "$DIR/venv" ]; then
    echo ""
    echo "[1/4] Creating virtual environment..."
    python3 -m venv "$DIR/venv"
else
    echo "[1/4] Virtual environment already exists."
fi

# 2. Install requirements
echo ""
echo "[2/4] Installing/upgrading requirements..."
"$DIR/venv/bin/pip" install --only-binary :all: "litellm>=1.60.0"
"$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"

# 3. Make wrappers executable
echo ""
echo "[3/4] Granting executable permissions to launcher scripts..."
chmod +x "$DIR/terminal/opendoor"
echo "Done."

# 4. Add to PATH in shell profiles
echo ""
echo "[4/4] Setting up PATH environment variable..."
ADDED=0
DETECTED_SHELLS=""

# Check zsh
if [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "$DIR/terminal" "$HOME/.zshrc"; then
        echo "export PATH=\"\$PATH:$DIR/terminal\"" >> "$HOME/.zshrc"
        DETECTED_SHELLS="$DETECTED_SHELLS .zshrc"
        ADDED=1
    fi
fi

# Check bash
if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "$DIR/terminal" "$HOME/.bashrc"; then
        echo "export PATH=\"\$PATH:$DIR/terminal\"" >> "$HOME/.bashrc"
        DETECTED_SHELLS="$DETECTED_SHELLS .bashrc"
        ADDED=1
    fi
fi

# Check profile
if [ -f "$HOME/.profile" ]; then
    if ! grep -q "$DIR/terminal" "$HOME/.profile"; then
        echo "export PATH=\"\$PATH:$DIR/terminal\"" >> "$HOME/.profile"
        DETECTED_SHELLS="$DETECTED_SHELLS .profile"
        ADDED=1
    fi
fi

if [ $ADDED -eq 1 ]; then
    echo "Added OpenDoor terminal directory to PATH in:$DETECTED_SHELLS"
    echo "Please restart your shell or run: source <profile_file>"
else
    echo "OpenDoor terminal directory is already in your shell profiles PATH."
fi

# 5. Launch configuration wizard
echo ""
echo "Starting configuration wizard..."
if [ -f "$DIR/venv/bin/python" ]; then
    "$DIR/venv/bin/python" "$DIR/terminal/setup.py"
else
    python3 "$DIR/terminal/setup.py"
fi

echo ""
echo "OpenDoor setup complete."
echo "Please restart your terminal to apply PATH changes."
echo ""
read -p "Would you like to run 'opendoor launch' now? (Y/n): " -r RUN_NOW
if [[ "$RUN_NOW" =~ ^[Yy]$ ]] || [[ -z "$RUN_NOW" ]]; then
    "$DIR/terminal/opendoor" launch
fi
