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
        self.vpn_manager = VPNManager(room_data)
        self.is_host = room_data.get('owner_username') == user_username

        file_path = os.path.join(os.getcwd(), 'ui', 'room_window.ui')
        self.ui = uic.loadUi(file_path, self)

        self.setup_ui()
        self.setup_connections()

        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(30000)

        self.setAttribute(Qt.WA_DeleteOnClose)

        QTimer.singleShot(1000, self.connect_to_vpn)

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
            self.lbl_vpn_info.setText("VPN Status: Connecting...")
        QTimer.singleShot(1000, self.connect_to_vpn)

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
        socket_manager.on('join_success', lambda data: self.handle_join_response(data), namespace="/game")
        socket_manager.on('new_message', self.log_and_emit(self.message_received), namespace="/game")
        socket_manager.on('user_joined', self.log_and_emit(self.player_joined), namespace="/game")
        socket_manager.on('user_left', self.log_and_emit(self.player_left), namespace="/game")
        socket_manager.on('update_players', lambda data: self.log_event('update_players', data) or self.update_players_signal.emit(data.get('players', [])), namespace="/game")
        socket_manager.on('host_changed', self.log_and_emit(self.host_changed), namespace="/game")
        socket_manager.on('room_closed', self.log_and_emit(self.room_closed_signal), namespace="/game")
        socket_manager.on('game_started', self.on_game_started, namespace="/game")

        QTimer.singleShot(2000, self.emit_join_request)

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
        self.room_data.update({
            'vpn_hub': response.get('vpn_hub'),
            'vpn_username': response.get('vpn_username'),
            'vpn_password': response.get('vpn_password'),
            'server_ip': response.get('server_ip'),
            'port': response.get('port')
        })

        host_tag = "👑 " if response.get('is_host', False) else ""
        self.add_chat_message(f"🟢 Connected as {host_tag}{self.user_username}<br>")
        self.update_players_signal.emit(self.players)
        QTimer.singleShot(1000, self.connect_to_vpn)

    def connect_to_vpn(self):
        vpn_info = self.room_data.get('vpn_info', self.room_data)
        self.vpn_status_signal.emit("VPN Status: Connecting...")
        success = self.vpn_manager.connect(vpn_info)
        if success:
            self.vpn_status_signal.emit("VPN Status: Connected")
        else:
            self.vpn_status_signal.emit("VPN Status: Failed to connect")
            self.show_warning_signal.emit("VPN Error", "Failed to connect to VPN.")

    def update_vpn_label(self, status_text):
        if hasattr(self, 'lbl_vpn_info'):
            self.lbl_vpn_info.setText(status_text)

    def disconnect_vpn(self):
        try:
            self.vpn_manager.disconnect()
            self.vpn_status_signal.emit("VPN Status: Disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting VPN: {e}")

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
        QTimer.singleShot(1000, lambda: socket_manager.emit("heartbeat", {
            "room_id": self.room_id,
            "username": self.user_username
        }, namespace="/game"))

    def render_players_list(self, players):
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
