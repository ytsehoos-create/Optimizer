#!/bin/bash
# Double-click this file on Mac to launch the optimizer UI.
# If Python is not found, install it from https://www.python.org

cd "$(dirname "$0")"

# Use python3 if available, fall back to python
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  osascript -e 'display alert "Python not found" message "Install Python 3 from python.org then try again."'
  exit 1
fi

# Install dependencies if needed (silent if already installed)
"$PYTHON" -m pip install -q -r requirements.txt

# Launch the UI
"$PYTHON" app.py
