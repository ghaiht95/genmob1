import sys
import os
import socketio
import subprocess
import time
import logging
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer, Qt, pyqtSlot
from PyQt5.QtGui import QTextCursor
from urllib.parse import urlparse
from datetime import datetime

from vpn_manager import VPNManager
from api_client import api_client
from socket_client import socket_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RoomWindow(QtWidgets.QMainWindow):
    room_closed = QtCore.pyqtSignal()
    message_received = QtCore.pyqtSignal(dict)
    player_joined = QtCore.pyqtSignal(dict)
    player_left = QtCore.pyqtSignal(dict)
    players_updated = QtCore.pyqtSignal(dict)
    host_changed = QtCore.pyqtSignal(dict)
    room_closed_signal = QtCore.pyqtSignal(dict)
    update_chat_signal = QtCore.pyqtSignal(str)
    show_warning_signal = QtCore.pyqtSignal(str, str)
    join_response_received = QtCore.pyqtSignal(dict)
    vpn_status_signal = QtCore.pyqtSignal(str)
    update_players_signal = QtCore.pyqtSignal(list)

    def __init__(self, room_data, user_username, access_token=None):
        super().__init__()
        if not isinstance(room_data, dict):
            raise ValueError("room_data must be a dictionary")

        self.room_data = room_data
        self.room_id = str(room_data.get("id", room_data.get("room_id", "")))
        self.user_username = user_username
        self.access_token = access_token
        self.players = []
        self.vpn_manager = None  # Will be created later when VPN info is available
        self.is_host = room_data.get('owner_username') == user_username

        file_path = os.path.join(os.getcwd(), 'ui', 'room_window.ui')
        self.ui = uic.loadUi(file_path, self)

        self.setup_ui()
        self.setup_connections()

        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(30000)

        self.setAttribute(Qt.WA_DeleteOnClose)

    def setup_ui(self):
        self.chat_display.setReadOnly(True)
        self.chat_display.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.chat_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.list_players = self.findChild(QtWidgets.QListWidget, 'list_players')
        self.list_players.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setWindowTitle(f"Room: {self.room_data.get('name', 'Unknown')}")
        if hasattr(self, 'btn_start'):
            self.btn_start.setEnabled(self.is_host)
        if hasattr(self, 'lbl_vpn_info'):
            self.lbl_vpn_info.setText("VPN Status: Waiting for room data...")

    def setup_connections(self):
        if hasattr(self, 'btn_send'):
            self.btn_send.clicked.connect(self.send_message)
        if hasattr(self, 'chat_input'):
            self.chat_input.returnPressed.connect(self.send_message)
        if hasattr(self, 'btn_leave'):
            self.btn_leave.clicked.connect(self.leave_room)
        if hasattr(self, 'btn_start'):
            self.btn_start.clicked.connect(self.start_game)

        self.message_received.connect(self.on_receive_message)
        self.player_joined.connect(self.on_user_joined)
        self.player_left.connect(self.on_user_left)
        self.host_changed.connect(self.on_host_changed)
        self.room_closed_signal.connect(self.on_room_closed)
        self.update_chat_signal.connect(self._update_chat_safe)
        self.show_warning_signal.connect(self.show_warning_box)
        self.join_response_received.connect(self.handle_join_response)
        self.vpn_status_signal.connect(self.update_vpn_label)
        self.update_players_signal.connect(self.render_players_list)

        socket_manager.on('connect', self.on_socket_connect, namespace="/game")
        socket_manager.on('disconnect', self.on_socket_disconnect, namespace="/game")
        socket_manager.on('error', self.on_socket_error)
        socket_manager.on('join_success', lambda data: self.join_response_received.emit(data), namespace="/game")
        socket_manager.on('new_message', self.log_and_emit(self.message_received), namespace="/game")
        socket_manager.on('user_joined', self.log_and_emit(self.player_joined), namespace="/game")
        socket_manager.on('user_left', self.log_and_emit(self.player_left), namespace="/game")
        socket_manager.on('update_players', lambda data: self.log_event('update_players', data) or self.update_players_signal.emit(data.get('players', [])), namespace="/game")
        socket_manager.on('host_changed', self.log_and_emit(self.host_changed), namespace="/game")
        socket_manager.on('room_closed', self.log_and_emit(self.room_closed_signal), namespace="/game")
        socket_manager.on('game_started', self.on_game_started, namespace="/game")

        # Use Qt's thread-safe signal mechanism instead of QTimer.singleShot for initial join
        QtCore.QMetaObject.invokeMethod(
            self,
            "_delayed_join_request",
            QtCore.Qt.QueuedConnection
        )

    def emit_join_request(self):
        if socket_manager.connected:
            logger.info("[📤] Sending join event")
            socket_manager.emit("join", {
                "room_id": self.room_id,
                "username": self.user_username
            }, namespace="/game")

    def log_event(self, name, data):
        logger.info(f"[📥 RECEIVED] {name}: {data}")

    def log_and_emit(self, signal):
        def wrapper(data):
            signal.emit(data)
        return wrapper

    def on_room_closed(self, data):
        logger.info(f"[📥 RECEIVED] room_closed: {data}")
        QMessageBox.information(self, "Room Closed", "The room has been closed by the host.")
        self.close()

    def on_socket_connect(self):
        logger.info("[🟢 SOCKET CONNECTED]")
        self.emit_join_request()

    def on_socket_disconnect(self):
        logger.info("[🔌 SOCKET DISCONNECTED]")
        self.add_chat_message("🔴 Disconnected from server<br>")

    def on_socket_error(self, error):
        logger.error(f"[❌ SOCKET ERROR]: {error}")
        QMessageBox.critical(self, "Connection Error", f"Socket error: {error}")
        self.close()

    def send_heartbeat(self):
        if socket_manager.connected:
            socket_manager.emit('heartbeat', {
                'room_id': self.room_id,
                'username': self.user_username
            }, namespace="/game")

    def handle_join_response(self, response):
        logger.info(f"[📥 RECEIVED] join_success: {response}")
        if not response or not response.get('success', False):
            QMessageBox.critical(self, "Error", f"Failed to join room: {response.get('error', 'Unknown error')}")
            self.close()
            return

        self.players = response.get('players', [])
        
        # Socket.io join only succeeds after HTTP join, so we should already have VPN data
        # No need to update VPN data from socket.io response since it doesn't contain VPN data
        host_tag = "👑 " if response.get('is_host', False) else ""
        self.add_chat_message(f"🟢 Connected as {host_tag}{self.user_username}<br>")
        self.update_players_signal.emit(self.players)
        
        # Try to connect to VPN using existing VPN data
        if self.room_data.get('vpn_info') or any(self.room_data.get(key) for key in ['network_name', 'private_key', 'server_public_key', 'server_ip']):
            # Use Qt's thread-safe signal mechanism instead of QTimer.singleShot
            QtCore.QMetaObject.invokeMethod(
                self, 
                "connect_to_vpn", 
                QtCore.Qt.QueuedConnection
            )
        else:
            self.vpn_status_signal.emit("VPN Status: No VPN network available")
            logger.info("No VPN data available - continuing without VPN")

    @pyqtSlot()
    def connect_to_vpn(self):
        self.vpn_status_signal.emit("VPN Status: Checking existing connections...")
        
        # Update room_data with VPN info before connecting
        if hasattr(self, 'room_data'):
            # Get VPN info from the vpn_info dictionary if it exists, otherwise from root level
            vpn_info_dict = self.room_data.get('vpn_info', {})
            vpn_info = {
                'network_name': vpn_info_dict.get('network_name') or self.room_data.get('network_name'),
                'private_key': vpn_info_dict.get('private_key') or self.room_data.get('private_key'),
                'public_key': vpn_info_dict.get('public_key') or self.room_data.get('public_key'),
                'server_public_key': vpn_info_dict.get('server_public_key') or self.room_data.get('server_public_key'),
                'server_ip': vpn_info_dict.get('server_ip') or self.room_data.get('server_ip'),
                'port': vpn_info_dict.get('port') or self.room_data.get('port', 51820),
                'allowed_ips': vpn_info_dict.get('allowed_ips') or self.room_data.get('allowed_ips')
            }
            self.room_data['vpn_info'] = vpn_info
            
            # Check if we have any VPN info at all (exclude port from the check since it has a default value)
            required_fields = ['network_name', 'private_key', 'server_public_key', 'server_ip']
            has_vpn_info = all(vpn_info.get(field) for field in required_fields)
            
            if not has_vpn_info:
                missing_fields = [field for field in required_fields if not vpn_info.get(field)]
                self.vpn_status_signal.emit("VPN Status: No VPN network available")
                logger.info(f"No VPN network configured for this room - missing fields: {missing_fields}")
                return
            
            # Create or recreate VPN manager with updated room data
            if self.vpn_manager:
                # Disconnect existing VPN if any
                logger.info("Disconnecting existing VPN connection...")
                self.vpn_status_signal.emit("VPN Status: Disconnecting old connection...")
                self.vpn_manager.disconnect(cleanup=True)  # Full cleanup
            
            # Create new VPN manager
            self.vpn_manager = VPNManager(self.room_data)
            
            # Log VPN configuration for debugging
            logger.info(f"VPN Configuration:")
            logger.info(f"  Network: {vpn_info.get('network_name', 'N/A')}")
            logger.info(f"  Server IP: {vpn_info.get('server_ip', 'N/A')}")
            logger.info(f"  Port: {vpn_info.get('port', 'N/A')}")
            logger.info(f"  Private Key: {'Present' if vpn_info.get('private_key') else 'Missing'}")
            logger.info(f"  Server Public Key: {'Present' if vpn_info.get('server_public_key') else 'Missing'}")
            logger.info(f"  Allowed IPs: {vpn_info.get('allowed_ips', 'N/A')}")
        
        # Update status and connect
        self.vpn_status_signal.emit("VPN Status: Connecting...")
        
        # Call connect without any arguments (only self)
        success = self.vpn_manager.connect()
        if success:
            self.vpn_status_signal.emit("VPN Status: Connected ✅")
            self.add_chat_message("🔐 <span style='color: green;'>VPN connected successfully!</span><br>")
            
            # Get tunnel info for display
            tunnel_info = self.vpn_manager.get_tunnel_info()
            network_name = tunnel_info.get('network_name', 'Unknown')
            self.add_chat_message(f"🌐 Network: <span style='color: blue;'>{network_name}</span><br>")
        else:
            # Check if it's missing VPN info or a real connection failure
            vpn_info = self.room_data.get('vpn_info', {})
            required_fields = ['server_ip', 'private_key', 'server_public_key']
            missing_fields = [field for field in required_fields if not vpn_info.get(field)]
            
            if missing_fields:
                self.vpn_status_signal.emit("VPN Status: No VPN network available")
                logger.info(f"VPN connection skipped - missing required fields: {missing_fields}")
                self.add_chat_message("ℹ️ <span style='color: orange;'>No VPN network configured for this room</span><br>")
            else:
                self.vpn_status_signal.emit("VPN Status: Failed to connect ❌")
                self.add_chat_message("⚠️ <span style='color: red;'>VPN connection failed</span><br>")
                
                # Show error message for actual connection failures
                error_msg = """Failed to connect to VPN.

This could be due to:
1. WireGuard not being installed or accessible
2. Insufficient administrator privileges  
3. Network connectivity issues
4. Old tunnels interfering with connection

The room will work without VPN, but you won't be able to connect to game servers.

To resolve:
- Make sure you run the application as administrator
- Check that WireGuard is properly installed
- Try running 'python wireguard_config.py' to configure WireGuard path"""
                self.show_warning_signal.emit("VPN Connection Failed", error_msg)

    def update_vpn_label(self, status_text):
        if hasattr(self, 'lbl_vpn_info'):
            self.lbl_vpn_info.setText(status_text)

    def disconnect_vpn(self):
        try:
            if self.vpn_manager:
                logger.info("Disconnecting VPN...")
                self.vpn_status_signal.emit("VPN Status: Disconnecting...")
                self.vpn_manager.disconnect(cleanup=True)  # Full cleanup when leaving room
                self.vpn_status_signal.emit("VPN Status: Disconnected")
                self.add_chat_message("🔓 <span style='color: orange;'>VPN disconnected</span><br>")
            else:
                logger.info("VPN manager not initialized, nothing to disconnect")
        except Exception as e:
            logger.error(f"Error disconnecting VPN: {e}")
            self.add_chat_message("⚠️ <span style='color: red;'>Error disconnecting VPN</span><br>")

    def send_message(self):
        message = self.chat_input.text().strip()
        if message and socket_manager.connected:
            socket_manager.emit('send_message', {
                'room_id': self.room_id,
                'username': self.user_username,
                'message': message
            }, namespace="/game")
            self.chat_input.clear()

    def on_receive_message(self, data):
        logger.info(f"[📥 RECEIVED] new_message: {data}")
        username = data.get('username', 'Unknown')
        message = data.get('message', '')
        timestamp = data.get('created_at', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%H:%M:%S")
                formatted_message = f"[{formatted_time}] {username}: {message}"
            except:
                formatted_message = f"{username}: {message}"
        else:
            formatted_message = f"{username}: {message}"
        self.add_chat_message(formatted_message + "<br>")

    def on_user_joined(self, data):
        logger.info(f"[📥 RECEIVED] user_joined: {data}")
        username = data.get('username', 'Unknown')
        self.add_chat_message(f"👋 {username} joined the room<br>")
        self.request_players_update()

    def on_user_left(self, data):
        logger.info(f"[📥 RECEIVED] user_left: {data}")
        username = data.get('username', 'Unknown')
        self.add_chat_message(f"👋 {username} left the room<br>")
        self.request_players_update()

    def request_players_update(self):
        # Use Qt's thread-safe signal mechanism instead of QTimer.singleShot
        QtCore.QMetaObject.invokeMethod(
            self,
            "_send_heartbeat_delayed",
            QtCore.Qt.QueuedConnection
        )
    
    @pyqtSlot()
    def _send_heartbeat_delayed(self):
        """Helper method to send heartbeat from main thread"""
        if socket_manager.connected:
            socket_manager.emit("heartbeat", {
                "room_id": self.room_id,
                "username": self.user_username
            }, namespace="/game")

    def render_players_list(self, players):
        """Render players list in a thread-safe manner"""
        # Ensure this runs in the main thread
        if not QtCore.QThread.currentThread() == QtWidgets.QApplication.instance().thread():
            QtCore.QMetaObject.invokeMethod(
                self,
                "_render_players_list_safe",
                QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(list, players)
            )
            return
        
        self._render_players_list_safe(players)
    
    @pyqtSlot(list)
    def _render_players_list_safe(self, players):
        """Thread-safe version of render_players_list"""
        self.players = players  # تأكد من تحديثهم
        self.list_players.clear()
        for player in players:
            username = player.get('username', 'Unknown')
            is_host = player.get('is_host', False)
            if username == self.user_username:
                self.is_host = is_host
                if hasattr(self, 'btn_start'):
                    self.btn_start.setEnabled(self.is_host)

            display_name = f"👑 {username}" if is_host else username
            item = QtWidgets.QListWidgetItem(display_name)
            self.list_players.addItem(item)

    def start_game(self):
        if self.is_host:
            socket_manager.emit('start_game', {'room_id': self.room_id}, namespace="/game")

    def on_game_started(self, data):
        logger.info(f"[📥 RECEIVED] game_started: {data}")
        QMessageBox.information(self, "Game Started", "The game has started!")

    def leave_room(self):
        try:
            self.disconnect_vpn()
            if socket_manager.connected:
                socket_manager.emit('leave', {
                    'room_id': self.room_id,
                    'username': self.user_username
                }, namespace="/game")
            self.close()
        except Exception as e:
            logger.error(f"Error leaving room: {e}")
            self.show_warning_signal.emit("Error", f"Error leaving room: {e}")
            self.close()

    def closeEvent(self, event):
        self.leave_room()
        self.heartbeat_timer.stop()
      
        self.room_closed.emit()
        event.accept()

    def on_host_changed(self, data):
        logger.info(f"[📥 RECEIVED] host_changed: {data}")
        new_host = data.get('new_host', 'Unknown')
        self.is_host = new_host == self.user_username
        if hasattr(self, 'btn_start'):
            self.btn_start.setEnabled(self.is_host)
        self.add_chat_message(f"👑 Host changed to: {new_host}<br>")
        self.request_players_update()


    @pyqtSlot(str)
    def _update_chat_safe(self, html_message):
        if hasattr(self, 'chat_display'):
            self.chat_display.append(html_message)
            self.chat_display.moveCursor(QTextCursor.End)

    def add_chat_message(self, html_message):
        self.update_chat_signal.emit(html_message)

    def show_warning_box(self, title, message):
        QMessageBox.warning(self, title, message)

    @pyqtSlot()
    def _delayed_join_request(self):
        """Helper method to send initial join request from main thread after 2 second delay"""
        QTimer.singleShot(2000, self.emit_join_request)
