#SHARED.PY
import logging
import socketio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create SocketIO server with full debug logging
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    ping_timeout=60,
    logger=True,           # Enable socketio internal logging
    engineio_logger=True   # Enable engineio internal logging
)

NAMESPACE = "/game"

# Session storage for keeping track of users and their rooms
client_rooms = {}  # Maps sid to {username, room_id}
last_heartbeat = {}  # Store last heartbeat time for each client 