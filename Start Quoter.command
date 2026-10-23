#!/bin/bash

# Finder may launch this file from a different working folder.
cd -- "$(dirname -- "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is needed to run the quoter. Install it from https://www.python.org/downloads/macos/"
    read -r -p "Press Return to close this window. "
    exit 1
fi

echo "Starting Charlottesville Transportation Quoter..."
echo "Your browser will open at http://127.0.0.1:8765"
echo "Keep this window open. Press Control+C here to stop the app."
echo

python3 app.py
quoter_status=$?

if [ "$quoter_status" -ne 0 ] && [ "$quoter_status" -ne 130 ]; then
    echo
    echo "The quoter stopped with an error. See the message above."
    read -r -p "Press Return to close this window. "
fi

exit "$quoter_status"
