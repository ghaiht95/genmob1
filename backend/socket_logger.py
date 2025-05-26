import logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Configure logger
socket_logger = logging.getLogger('socket_events')
socket_logger.setLevel(logging.DEBUG)

# Create file handler
log_file = os.path.join(logs_dir, 'socket_events.log')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
socket_logger.addHandler(file_handler)
socket_logger.addHandler(console_handler)

def log_connection(sid, environ):
    """Log new socket connection"""
    socket_logger.info(f"New connection - SID: {sid}")
    socket_logger.debug(f"Connection environment: {environ}")

def log_disconnection(sid, client_rooms):
    """Log socket disconnection"""
    socket_logger.info(f"Disconnection - SID: {sid}")
    socket_logger.debug(f"Client rooms state: {client_rooms}")

def log_join_event(sid, data):
    """Log room join event"""
    socket_logger.info(f"Join event - SID: {sid}, Data: {data}")

def log_leave_event(sid, data):
    """Log room leave event"""
    socket_logger.info(f"Leave event - SID: {sid}, Data: {data}")

def log_heartbeat(sid, data):
    """Log heartbeat event"""
    socket_logger.debug(f"Heartbeat - SID: {sid}, Data: {data}")

def log_message(sid, data):
    """Log chat message event"""
    socket_logger.info(f"New message - SID: {sid}, Data: {data}")

def log_player_check(sid, data):
    """Log player check event"""
    socket_logger.info(f"Player check - SID: {sid}, Data: {data}")

def log_game_start(sid, data):
    """Log game start event"""
    socket_logger.info(f"Game start - SID: {sid}, Data: {data}")

def log_error(event_type, sid, error):
    """Log socket errors"""
    socket_logger.error(f"Error in {event_type} - SID: {sid}, Error: {str(error)}")

def log_debug(message, data=None):
    """Log debug messages"""
    if data:
        socket_logger.debug(f"{message} - Data: {data}")
    else:
        socket_logger.debug(message) 