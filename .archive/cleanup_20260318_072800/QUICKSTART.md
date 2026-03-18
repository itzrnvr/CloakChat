#!/bin/bash

echo "🔧 Quick Commands for Project Spect"
echo "==================================="
echo ""

echo "🛑 To STOP all servers:"
echo "  pkill -f uvicorn"
echo "  pkill -f 'bun.*dev'"
echo ""

echo "▶️  To START backend:"
echo "  cd /Users/aditiaryan/Documents/code/capstone/project2/project-spect"
echo "  PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload"
echo ""

echo "▶️  To START frontend:"
echo "  cd /Users/aditiaryan/Documents/code/capstone/project2/project-spect/frontend"
echo "  bun run dev"
echo ""

echo "🚀 To START both (using script):"
echo "  cd /Users/aditiaryan/Documents/code/capstone/project2/project-spect"
echo "  ./start-fresh.sh"
echo ""

echo "💡 Other commands:"
echo "  Test backend: curl http://localhost:8001/api/health"
echo "  View config: curl http://localhost:8001/api/config"
echo "  List strategies: curl http://localhost:8001/api/strategies"
echo ""