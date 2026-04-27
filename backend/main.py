import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import load_config
from backend.routes import chat, config, sessions

# Configure logging before app starts
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(title="CloakChat", description="Privacy-preserving AI chat", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,     prefix="/api", tags=["chat"])
app.include_router(config.router,   prefix="/api", tags=["config"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    cfg = load_config()
    uvicorn.run(
        "backend.main:app",
        host=cfg.server.get("host", "0.0.0.0"),
        port=cfg.server.get("port", 8012),
        reload=True,
        log_level="info",
        access_log=True,
    )
