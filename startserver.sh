#!/bin/bash

echo "🚀 Starting Food2Guide servers..."

# Kill any existing processes on ports 8000 and 3000
echo "🔄 Killing existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Wait a moment for ports to be freed
sleep 2

# Start backend server
echo "🐍 Starting backend server on port 8000..."
source /Users/henrikpetersson/Desktop/Webbprojekt/makeiteasy/whisper_env/bin/activate
python -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend server
echo "⚛️  Starting frontend server on port 3000..."
npm start &
FRONTEND_PID=$!

# Wait for both servers to start
echo "⏳ Waiting for servers to start..."
sleep 10

# Test if servers are running
echo "🔍 Testing servers..."
if curl -s -o /dev/null -w "Backend: %{http_code}\n" http://localhost:8000 | grep -q "200"; then
    echo "✅ Backend server is running on http://localhost:8000"
else
    echo "❌ Backend server failed to start"
fi

if curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://localhost:3000 | grep -q "200"; then
    echo "✅ Frontend server is running on http://localhost:3000"
else
    echo "❌ Frontend server failed to start"
fi

echo "🎉 Both servers should now be running!"
echo "📱 Open http://localhost:3000 in your browser"
echo ""
echo "To stop servers, press Ctrl+C or run: kill $BACKEND_PID $FRONTEND_PID"

# Keep script running and handle Ctrl+C
trap "echo '🛑 Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
