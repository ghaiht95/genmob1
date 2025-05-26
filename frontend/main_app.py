# main_app.py
import os
import sys
import ctypes
import requests
import subprocess
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QMessageBox, QDialog, QInputDialog, QListWidgetItem, QMenu
from PyQt5.QtGui import QTextCursor
from PyQt5.QtCore import QMetaType, QTimer, QThread, pyqtSignal, Qt
from dialogs.room_settings_dialog import RoomSettingsDialog
from room_window import RoomWindow    
from settings_window import SettingsWindow
from translator import Translator, _
from dotenv import load_dotenv
from dialogs.friends import FriendsDialog
from api_client import api_client
import time
from socket_client import socket_manager



load_dotenv()

# 🟡 قراءة عنوان الـ API من المتغير البيئي
API_BASE_URL = os.getenv("API_BASE_URL")
# --------- تشغيل كمسؤول تلقائيًا ---------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit()
# -------------------------------------------







class RoomLoader(QThread):
    rooms_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, access_token):
        super().__init__()
        self.access_token = access_token

    def run(self):
        try:
            api_client.set_token(self.access_token)
            data = api_client.get("/rooms/")
            rooms = data["rooms"]
            self.rooms_loaded.emit(rooms)
        except Exception as e:
            self.error_occurred.emit(str(e))

class MainApp(QtWidgets.QMainWindow):
    def __init__(self, user_data):
        super().__init__()
        import os
        file_path = os.path.join(os.getcwd(), 'ui', 'main_window.ui')
        self.ui = uic.loadUi(file_path, self)
       
        self.user_data = user_data
        self.access_token = user_data.get('access_token', '')
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # إضافة متغير للتحكم في محاولات الانضمام
        self._last_join_attempt = 0
        self._join_cooldown = 2000  # 2 seconds cooldown
        
        # ترجمة واجهة المستخدم
        self.translate_ui()
        
        self.lbl_welcome.setText(_("ui.main_window.welcome", "مرحباً، {username}", username=user_data['username']))
        self.btn_create.clicked.connect(self.create_room)
        self.btn_logout.clicked.connect(self.logout)

        # أزرار قائمة الأصدقاء
        self.btn_friends.clicked.connect(self.show_friends_dialog)
        self.btn_add_friend.clicked.connect(self.add_friend_dialog)
        
        # ربط زر الإعدادات
        self.btn_settings.clicked.connect(self.show_settings)

        self.current_proc = None
        self.room_win = None
        self.last_rooms = []

        # إنشاء قائمة الغرف باستخدام QListWidget
        self.roomsWidget = QtWidgets.QListWidget()
        self.roomsWidget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.roomsWidget.itemDoubleClicked.connect(self.on_room_item_clicked)
        
        # إضافة الخصائص للقائمة
        self.roomsWidget.setSpacing(5)
        self.roomsWidget.setIconSize(QtCore.QSize(48, 48))
        self.roomsWidget.setWordWrap(True)
        self.roomsWidget.setStyleSheet("""
            QListWidget::item { 
                border: 1px solid #ccc; 
                border-radius: 5px; 
                padding: 10px; 
                margin: 5px;
                background-color: #f9f9f9;
            }
            QListWidget::item:selected { 
                background-color: #daeaf7; 
            }
            QListWidget::item:hover { 
                background-color: #eaf5ff; 
            }
        """)
        
        # إضافة القائمة إلى UI
        self.ui.roomsLayout.addWidget(self.roomsWidget)
        
        # قاموس لتخزين بيانات الغرف
        self.rooms_data = {}

        # جلب عنوان السيرفر للسوكيت
        api_client.set_token(self.access_token)
        try:
            data = api_client.get("/rooms/status")
            self.server_url = data.get("socket_url")
            if data.get("status") == "ok" and self.server_url:
                socket_manager.connect(self.server_url)
                socket_manager.on('update_rooms', lambda data: self.update_rooms())
        except Exception as e:
            print(f"[SocketIO] Failed to connect: {e}")

        self.load_rooms()

    def translate_ui(self):
        """ترجمة عناصر واجهة المستخدم"""
        self.setWindowTitle(_("ui.main_window.title", "القائمة الرئيسية"))
        self.btn_create.setText(_("ui.main_window.create_room", "➕ إنشاء غرفة"))
        self.btn_logout.setText(_("ui.main_window.logout", "🚪 تسجيل خروج"))
        self.btn_friends.setText(_("ui.main_window.friends", "👥 الأصدقاء"))
        self.btn_add_friend.setText(_("ui.main_window.add_friend", "➕ إضافة صديق"))
        self.btn_settings.setText(_("ui.main_window.settings", "⚙️ الإعدادات"))

    def load_rooms(self):
        self.room_loader = RoomLoader(self.access_token)
        self.room_loader.rooms_loaded.connect(self.update_rooms_list)
        self.room_loader.error_occurred.connect(self.show_error)
        self.room_loader.start()

    def update_rooms_list(self, rooms):
        self.roomsWidget.clear()
        self.rooms_data = {}
        for room in rooms:
            try:
                if not isinstance(room, dict):
                    print(f"Warning: room is not a dict, got {type(room)}")
                    continue
                
                # استخراج بيانات الغرفة
                room_id = room.get('id', room.get('room_id', ''))
                name = room.get('name') or room.get('room_name') or 'بدون اسم'

                is_private = room.get("is_private", False)
                current_players = room.get('current_players', 0)
                max_players = room.get('max_players', 8)
                owner = room.get('owner_username', '')
                
                # إنشاء نص الغرفة
                room_text = f"🏷️ {name}\n"
                room_text += f"👥 {current_players}/{max_players} | "
                room_text += "🔒 خاصة" if is_private else "🌐 عامة"
                room_text += f"\n👤 {owner}"
                
                # إضافة عنصر للقائمة
                item = QListWidgetItem(room_text)
                item.setData(QtCore.Qt.UserRole, room_id)  # تخزين معرف الغرفة
                
                # تخزين بيانات الغرفة في القاموس
                self.rooms_data[str(room_id)] = room
                
                self.roomsWidget.addItem(item)
            except Exception as e:
                print(f"Error adding room to list: {e}")
                continue

    def on_room_item_clicked(self, item):
        """معالجة النقر المزدوج على غرفة من القائمة"""
        room_id = item.data(QtCore.Qt.UserRole)
        room = self.rooms_data.get(str(room_id))
        
        if room:
            self.join_room_direct(room)

    def create_room(self):
        dlg = RoomSettingsDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        s = dlg.get_settings()
        if not s["name"]:
            return self.show_message("أدخل اسم الغرفة")
        
        payload = {
            "name":        s["name"],
            "description": s["description"],
            "is_private":  s["is_private"],
            "password":    s["password"],
            "max_players": s["max_players"]
        }

        def log_error(msg):
            with open("log.txt", "a", encoding="utf-8") as f:
                f.write(msg + "\n")

        try:
            api_client.set_token(self.access_token)
            data = api_client.post("/rooms/create_room", json=payload)
            # تجهيز معلومات الغرفة
            room_info = {
                "id": data.get("id", ""),
                "room_id": data.get("room_id", ""),
                "name": s["name"],
                "description": s["description"],
                "is_private": s["is_private"],
                "max_players": s["max_players"],
                "current_players": 1,
                "owner_username": self.user_data["username"],
                "vpn_info": {
                    "hub": data.get("vpn_hub", ""),
                    "username": data.get("vpn_username", ""),
                    "password": data.get("vpn_password", ""),
                    "server_ip": data.get("server_ip", ""),
                    "port": data.get("port", 443)
                }
            }
            self.open_room(room_info)
        except Exception as e:
            log_error(f"[RequestException] {e}")
            return self.show_message(f"خطأ في الإنشاء: {e}")
    def join_room_direct(self, room):
        # التحقق من وقت آخر محاولة انضمام
        current_time = int(time.time() * 1000)
        if current_time - self._last_join_attempt < self._join_cooldown:
            logger.warning("Join attempt too soon, ignoring")
            return
            
        self._last_join_attempt = current_time
        
        if room.get("is_private"):
            password, ok = QInputDialog.getText(self, "Room Password", "This room is private. Enter password:", QtWidgets.QLineEdit.Password)
            if not ok or not password:
                return
        else:
            password = ""
        
        try:
            api_client.set_token(self.access_token)
            data = api_client.post("/rooms/join_room", json={"room_id": room['id'], "password": password})

            # التعامل مع الأخطاء بناءً على محتوى dict
            if "detail" in data:
                error_msg = data["detail"]
                return self.show_message(f"خطأ: {error_msg}", "خطأ")
            
            # إذا كان المستخدم موجود بالفعل في الغرفة
            if data.get("message") == "You are already in this room. Using existing connection.":
                logger.info("User already in room, using existing connection")
                # تحديث بيانات الغرفة مع البيانات الحالية
                room_info = {
                    "id": room['id'],
                    "name": room.get('name', ''),
                    "description": room.get('description', ''),
                    "is_private": room.get('is_private', False),
                    "max_players": room.get('max_players', 8),
                    "current_players": room.get('current_players', 0),
                    "owner_username": room.get('owner_username', ''),
                    "vpn_info": {
                        "hub": data.get("vpn_hub", room.get("vpn_hub", "default")),
                        "username": data.get("vpn_username", room.get("vpn_username", "")),
                        "password": data.get("vpn_password", room.get("vpn_password", "")),
                        "server_ip": data.get("server_ip", room.get("server_ip", "")),
                        "port": data.get("port", room.get("port", 443))
                    },
                    "_already_joined": True  # Mark as already joined
                }
                self.open_room(room_info)
                return
            
            # تحديث بيانات الغرفة
            vpn_info = {
                "hub": data.get("vpn_hub", room.get("vpn_hub", "default")),
                "username": data.get("vpn_username", room.get("vpn_username", "")),
                "password": data.get("vpn_password", room.get("vpn_password", "")),
                "server_ip": data.get("server_ip", room.get("server_ip", "")),
                "port": data.get("port", room.get("port", 443))
            }
            
            room_info = {
                "id": room['id'],
                "name": room.get('name', ''),
                "description": room.get('description', ''),
                "is_private": room.get('is_private', False),
                "max_players": room.get('max_players', 8),
                "current_players": room.get('current_players', 0),
                "owner_username": room.get('owner_username', ''),
                "vpn_info": vpn_info,
                "_already_joined": True  # Mark as already joined
            }
            
            self.open_room(room_info)
        except Exception as e:
            with open("log.txt", "a", encoding="utf-8") as f:
                f.write(f"[Join Room Error] {e}\n")
            return self.show_message(f"خطأ في الانضمام: {e}", "خطأ")

    def open_room(self, room_info):
        if self.room_win:
            self.room_win.close()

        self.room_win = RoomWindow(room_info, self.user_data["username"], self.access_token)
        self.room_win.room_closed.connect(self.on_room_close)
        self.room_win.show()

    def on_room_close(self):
        # عرض النافذة الرئيسية قبل أي شيء آخر
        self.show()
        # تأكد أن النافذة في المقدمة
        self.raise_()
        self.activateWindow()
        # ثم تحديث الغرف وإعادة تشغيل الـ loader
        self.update_rooms()
        self.room_win = None

    def update_rooms(self):
        try:
            api_client.set_token(self.access_token)
            data = api_client.get("/rooms/")
            new_rooms = data["rooms"]
            if self.is_rooms_changed(new_rooms):
                self.update_rooms_list(new_rooms)
                self.last_rooms = new_rooms
                self.notify_change()
        except Exception:
            pass

    def is_rooms_changed(self, new_rooms):
        return new_rooms != self.last_rooms

    def notify_change(self):
        QMessageBox.information(self, _("ui.messages.update", "تحديث"), 
                               _("ui.messages.room_update", "📢 تم تحديث قائمة الغرف!"))

    def logout(self):
        if self.room_win:
            self.room_win.close()
        self.close()

    def show_message(self, msg, title="Info"):
        QMessageBox.information(self, _("ui.messages.info", title), msg)

    def show_error(self, message):
        self.show_message(message, "Error")

    def show_friends_dialog(self):
        dlg = FriendsDialog(self.user_data, self.access_token, self)
        dlg.exec_()

    def add_friend_dialog(self):
        username, ok = QInputDialog.getText(self, 
                                           _("ui.main_window.add_friend_title", "إضافة صديق"),
                                           _("ui.main_window.enter_friend_username", "أدخل اسم المستخدم:"))
        if ok and username:
            self.send_friend_request(username)

    def send_friend_request(self, friend_username):
        try:
            data = api_client.post("/friends/send_request", json={"friend_username": friend_username})
            if "detail" in data:
                error_msg = data["detail"]
                self.show_message(error_msg, "Error")
            else:
                self.show_message(_("ui.main_window.friend_request_sent", "تم إرسال طلب الصداقة بنجاح!"))
        except Exception as e:
            self.show_message(f"خطأ: {e}", "Error")

    def show_settings(self):
        """عرض نافذة الإعدادات"""
        settings_dialog = SettingsWindow(self)
        settings_dialog.exec_()

    def clear_rooms(self):
        """تنظيف قائمة الغرف"""
        self.roomsWidget.clear()
        self.rooms_data = {}

    def closeEvent(self, event):
        try:
        socket_manager.disconnect()
        except Exception as e:
            print(f"Error in closeEvent: {e}")
        event.accept()



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainApp({"username": "ali", "email": "ali@example.com"})
    win.show()
    sys.exit(app.exec_())