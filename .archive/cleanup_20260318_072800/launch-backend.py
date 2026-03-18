#!/usr/bin/env python3
"""
Simple launcher for Project Spect Backend without uvicorn issues.
"""

import sys
import os
import subprocess
import time
from pathlib import Path

def main():
    project_dir = Path("/Users/aditiaryan/Documents/code/capstone/project2/project-spect")
    os.chdir(project_dir)
    
    # Set Python path
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    
    # Kill existing process on port 8001
    try:
        result = subprocess.run(
            ["lsof", "-ti:8001"], 
            capture_output=True, 
            text=True
        )
        if result.stdout.strip():
            pid = result.stdout.strip()
            print(f"🔪 Killing existing process on port 8001 (PID: {pid})...")
            subprocess.run(["kill", "-9", pid], capture_output=True)
            time.sleep(2)
    except Exception as e:
        print(f"Note: Could not check port 8001: {e}")
    
    print("🚀 Starting Project Spect Backend...")
    print("📦 Using uvicorn without reload mode (more stable)")
    print("")
    
    # Run uvicorn directly without reload
    cmd = [
        "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8001",
        "--log-level", "info"
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Backend stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
