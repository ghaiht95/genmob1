import uvicorn

# Import the combined ASGI app (FastAPI + Socket.IO) from app_setup.py
from app_setup import socket_app

# The main guard for running Uvicorn
if __name__ == "__main__":
    uvicorn.run(
        socket_app, 
        host="0.0.0.0", 
        port=5000, 
        reload=True
    ) 