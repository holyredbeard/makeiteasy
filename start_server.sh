#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Load environment variables from .env file
if [ -f .env ]; then
    source .env
fi

echo "Starting backend server with Google OAuth configured..."
python main.py 