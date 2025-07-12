#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

echo "Starting backend server with Google OAuth configured..."
python main.py 