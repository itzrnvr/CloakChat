#!/bin/bash

PROJECT_DIR="/Users/aditiaryan/Documents/code/capstone/project2/project-spect"
BACKEND_PORT=8001
FRONTEND_PORT=5173

echo "🚀 Starting Project Spect"
echo "========================"
echo ""

# Function to kill process on a port
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "🔪 Killing existing process on port $port (PID: $pid)..."
        kill -9 $pid 2>/dev/null
        sleep 2
    fi
}

start_backend() {
    echo "📦 Starting backend server on port $BACKEND_PORT..."
    cd "$PROJECT_DIR"
    
    # Kill any existing backend
    kill_port $BACKEND_PORT
    
    if ! command -v uvicorn &> /dev/null; then
        echo "❌ uvicorn not found. Install with: uv add uvicorn"
        exit 1
    fi
    
    PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload &
    BACKEND_PID=$!
    echo "✅ Backend started (PID: $BACKEND_PID)"
    echo "   API: http://localhost:$BACKEND_PORT"
    echo "   Docs: http://localhost:$BACKEND_PORT/docs"
    echo ""
}

start_frontend() {
    echo "🎨 Starting frontend server on port $FRONTEND_PORT..."
    cd "$PROJECT_DIR/frontend"
    
    # Kill any existing frontend
    kill_port $FRONTEND_PORT
    
    if ! command -v bun &> /dev/null; then
        echo "❌ bun not found. Install from: https://bun.sh"
        exit 1
    fi
    
    bun run dev &
    FRONTEND_PID=$!
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
    echo "   App: http://localhost:$FRONTEND_PORT"
    echo ""
}

cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    if [ -n "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null; then
        echo "   Backend stopped"
    fi
    if [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null; then
        echo "   Frontend stopped"
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Checklist:"
echo "  • Python 3.12+ installed"
echo "  • Dependencies installed: uv sync"
echo "  • Bun 1.0+ installed"
echo "  • .env file configured (optional)"
echo "  • Model configured in config.yaml"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

start_backend

sleep 3

start_frontend

echo "✨ Both servers running!"
echo "========================"
echo ""
echo "🌐 App: http://localhost:$FRONTEND_PORT"
echo "📊 API: http://localhost:$BACKEND_PORT"
echo "📖 Docs: http://localhost:$BACKEND_PORT/docs"
echo ""
echo "Happy coding! 🎉"
echo ""

# Wait for backend to finish (or be killed)
wait $BACKEND_PID