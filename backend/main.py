import sys
import os
import logging
import socket

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from uvicorn.server import Server
from uvicorn.config import Config
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


class ReuseAddrServer(Server):
    def _bind_socket(self):
        sock = super()._bind_socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock


if __name__ == "__main__":
    cfg = load_config()
    reload_enabled = os.getenv("CLOAKCHAT_RELOAD", "0").lower() in {"1", "true", "yes"}
    config = Config(
        "backend.main:app",
        host=cfg.server.get("host", "0.0.0.0"),
        port=cfg.server.get("port", 8012),
        reload=reload_enabled,
        log_level="info",
        access_log=True,
    )
    server = ReuseAddrServer(config=config)
    server.run()
