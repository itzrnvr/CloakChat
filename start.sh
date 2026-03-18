#!/bin/bash

# CloakChat - Start Script
# Starts both backend and frontend servers

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8001
FRONTEND_PORT=5173

echo "🚀 Starting CloakChat"
echo "========================"
echo ""

# Function to kill process on a port
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null || echo "")
    if [ -n "$pid" ]; then
        echo "🔪 Killing existing process on port $port (PID: $pid)..."
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        echo "   Backend stopped"
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        echo "   Frontend stopped"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.12+"
    exit 1
fi

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "❌ Virtual environment not found. Run: python3 -m venv .venv"
    exit 1
fi

if ! command -v bun &> /dev/null; then
    echo "❌ Bun not found. Install from: https://bun.sh"
    exit 1
fi

echo "✅ Prerequisites OK"
echo ""

# Kill any existing processes
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# Start Backend
echo "📦 Starting backend server..."
cd "$PROJECT_DIR"
source .venv/bin/activate
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
python backend/main.py &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"
echo "   API: http://localhost:$BACKEND_PORT"
echo ""

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
sleep 3

# Start Frontend
echo "🎨 Starting frontend server..."
cd "$PROJECT_DIR/frontend"
bun run dev &
FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"
echo "   App: http://localhost:$FRONTEND_PORT"
echo ""

echo "✨ Both servers running!"
echo "========================"
echo ""
echo "🌐 Open: http://localhost:$FRONTEND_PORT"
echo "📊 API: http://localhost:$BACKEND_PORT"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait
