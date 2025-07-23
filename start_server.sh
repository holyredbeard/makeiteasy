#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    source .env
fi

echo "Starting backend server with Google OAuth configured..."
python main.py 