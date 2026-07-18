#!/bin/bash

set -e

# Find project root (parent of scripts folder)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_SCRIPT="$PROJECT_DIR/scripts/fetch_events.py"

echo "Project directory: $PROJECT_DIR"

# Enter project directory
cd "$PROJECT_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Run Python script
echo "Running Python script..."
python "$PYTHON_SCRIPT"

# Deactivate venv
deactivate

# Git operations
echo "Adding changes..."
git add .

echo "Committing changes..."
git commit -m "Automated update $(date '+%Y-%m-%d %H:%M:%S')" || echo "Nothing to commit"

echo "Pushing changes..."
git push

echo "Finished."
