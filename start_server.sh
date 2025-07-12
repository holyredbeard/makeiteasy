#!/bin/bash
export GOOGLE_CLIENT_ID="568199774089-mrtlrhkcb7sr3j2nhebk4dhq3odt9ud9.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="GOCSPX-nUlg"
export GOOGLE_REDIRECT_URI="http://localhost:3000"
export JWT_SECRET_KEY="your_super_secret_jwt_key_here_make_it_long_and_random_123456789"

echo "Starting backend server with Google OAuth configured..."
python main.py 