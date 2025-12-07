#!/bin/bash
set -e

echo "Installing/updating dependencies..."
pip install --no-cache-dir --upgrade pip setuptools wheel
echo "Installing project dependencies..."
pip install --no-cache-dir -e ".[dev]"
echo "Verifying a2a-sdk installation..."
python -c "import a2a; print('✓ a2a module imported successfully')" || (echo "✗ Failed to import a2a module" && pip list | grep -i a2a && exit 1)

echo "Starting application..."
exec "$@"

