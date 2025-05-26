from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtWidgets import QDialog, QMessageBox, QMenu, QListWidgetItem, QInputDialog
import requests
import os
from dialogs.search import UserSearchResultsDialog
from translator import _
from dotenv import load_dotenv
import sys
from PyQt5.QtCore import Qt
from api_client import api_client



load_dotenv()

# 🟡 قراءة عنوان الـ API من المتغير البيئي
API_BASE_URL = os.getenv("API_BASE_URL")

def log_error(msg):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


class FriendsDialog(QDialog):
    def __init__(self, user_data, access_token, parent=None):
        super().__init__(parent)
        self.user_data = user_data
        self.access_token = access_token
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
        self.load_ui()
        self.setup_ui()
        self.load_friends()

    def load_ui(self):
        ui_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "friends_dialog.ui")
        uic.loadUi(ui_file, self)

    def setup_ui(self):
        self.setWindowTitle(_("ui.friends.title", "الأصدقاء"))
        self.add_friend_btn.clicked.connect(self.add_friend)
        self.btnSearch.clicked.connect(self.search_users_dialog)
        self.accept_btn.clicked.connect(lambda: self.handle_pending_action("accept"))
        self.decline_btn.clicked.connect(lambda: self.handle_pending_action("decline"))
        self.cancel_btn.clicked.connect(self.handle_sent_action)
        self.refresh_btn.clicked.connect(self.load_data)
        
        # إضافة القوائم المنبثقة
        self.pendingList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pendingList.customContextMenuRequested.connect(self.show_pending_context_menu)
        self.sentList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sentList.customContextMenuRequested.connect(self.show_sent_context_menu)
        self.friendsList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.friendsList.customContextMenuRequested.connect(self.show_friend_context_menu)

    def load_friends(self):
        try:
            api_client.set_token(self.access_token)
            response = api_client.get("/friends/my_friends")
            if "friends" in response:
                self.update_friends_list(response["friends"])
            else:
                self.show_message(_("ui.friends.fetch_error", "فشل في جلب قائمة الأصدقاء."), "Error")
        except Exception as e:
            self.show_message(str(e), "Error")

    def update_friends_list(self, friends):
        self.friendsList.clear()
        for friend in friends:
            self.friendsList.addItem(f"{friend['username']} ({friend['email']})")

    def add_friend(self):
        username, ok = QtWidgets.QInputDialog.getText(
            self,
            _("ui.friends.add_friend", "إضافة صديق"),
            _("ui.friends.enter_username", "أدخل اسم المستخدم لصديقك:")
        )
        if ok and username:
            try:
                api_client.set_token(self.access_token)
                response = api_client.post("/friends/send_request", data={"friend_username": username})
                if response.get("message"):
                    self.show_message(_("ui.friends.request_sent", "تم إرسال طلب الصداقة بنجاح."))
                    self.load_friends()
                else:
                    error_msg = response.get("detail", _("ui.friends.request_failed", "فشل في إرسال طلب الصداقة."))
                    self.show_message(error_msg, "Error")
            except Exception as e:
                self.show_message(str(e), "Error")

    def remove_friend(self):
        selected_items = self.friendsList.selectedItems()
        if not selected_items:
            self.show_message(_("ui.friends.select_friend", "الرجاء اختيار صديق لإزالته."), "Warning")
            return

        friend_data = selected_items[0].text().split(" (")
        friend_username = friend_data[0]
        friend_email = friend_data[1].rstrip(")")
        
        try:
            api_client.set_token(self.access_token)
            # أولاً نحصل على قائمة الأصدقاء للحصول على الـ ID
            friends_response = api_client.get("/friends/my_friends")
            if "friends" in friends_response:
                friends = friends_response["friends"]
                friend = next((f for f in friends if f["username"] == friend_username), None)
                
                if friend:
                    response = api_client.post(f"/friends/remove_friend/{friend['id']}")
                    if response.get("message"):
                        self.show_message(_("ui.friends.removed", "تم إزالة الصديق بنجاح."))
                        self.load_friends()
                    else:
                        error_msg = response.get("detail", _("ui.friends.remove_failed", "فشل في إزالة الصديق."))
                        self.show_message(error_msg, "Error")
                else:
                    self.show_message(_("ui.friends.friend_not_found", "لم يتم العثور على الصديق."), "Error")
            else:
                self.show_message(_("ui.friends.fetch_error", "فشل في جلب قائمة الأصدقاء."), "Error")
        except Exception as e:
            self.show_message(str(e), "Error")

    def show_message(self, message, title="Info"):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information if title == "Info" else QMessageBox.Warning)
        msg.setText(message)
        msg.setWindowTitle(_("ui.friends.info" if title == "Info" else "ui.friends.error", title))
        msg.exec_()

    def translate_ui(self):
        self.setWindowTitle(_("ui.friends_dialog.title", "قائمة الأصدقاء"))
        self.tabWidget.setTabText(0, _("ui.friends_dialog.tab_friends", "الأصدقاء"))
        self.tabWidget.setTabText(1, _("ui.friends_dialog.tab_pending", "طلبات واردة"))
        self.tabWidget.setTabText(2, _("ui.friends_dialog.tab_sent", "طلبات مرسلة"))
        self.btnSearch.setText(_("ui.friends_dialog.btn_search", "🔍 بحث عن مستخدمين"))
        self.add_friend_btn.setText(_("ui.friends_dialog.add_friend", "➕ إضافة صديق"))
        self.accept_btn.setText(_("ui.friends_dialog.accept", "✅ قبول"))
        self.decline_btn.setText(_("ui.friends_dialog.decline", "❌ رفض"))
        self.cancel_btn.setText(_("ui.friends_dialog.cancel", "🚫 إلغاء الطلب"))

    def load_data(self):
        self.load_friends()
        self.load_pending_requests()
        self.load_sent_requests()

    def load_pending_requests(self):
        self.pendingList.clear()
        try:
            api_client.set_token(self.access_token)
            response = api_client.get("/friends/pending_requests")
            print("pending_requests response:", response)
            if "pending_requests" in response:
                requests = response["pending_requests"]
                for req in requests:
                    item = QListWidgetItem(f"{req['username']} ({req['email']})")
                    item.setData(QtCore.Qt.UserRole, req['request_id'])
                    self.pendingList.addItem(item)
        except Exception as e:
            self.show_message(str(e), "Error")

    def load_sent_requests(self):
        self.sentList.clear()
        try:
            api_client.set_token(self.access_token)
            response = api_client.get("/friends/sent_requests")
            print("sent_requests response:", response)
            if "sent_requests" in response:
                requests = response["sent_requests"]
                for req in requests:
                    item = QListWidgetItem(f"{req['username']} ({req['email']})")
                    item.setData(QtCore.Qt.UserRole, req['request_id'])
                    self.sentList.addItem(item)
        except Exception as e:
            self.show_message(str(e), "Error")

    def show_response_message(self, response, success_msg, error_msg, reload_func=None):
        if response.status_code == 200:
            QMessageBox.information(self, _("ui.common.info", "معلومة"), success_msg)
            if reload_func:
                reload_func()
        else:
            try:
                data = response.json()
                detail = data.get("detail") or data.get("error", "")
                QMessageBox.warning(self, _("ui.common.error", "خطأ"), f"{error_msg}\n{detail}")
            except:
                QMessageBox.warning(self, _("ui.common.error", "خطأ"), error_msg)

    def show_friend_context_menu(self, position):
        item = self.friendsList.itemAt(position)
        if not item:
            return

        friend_id = item.data(QtCore.Qt.UserRole)
        menu = QMenu()
        remove_action = menu.addAction(_("ui.friends_dialog.remove_friend", "🗑️ إزالة من الأصدقاء"))
        action = menu.exec_(self.friendsList.mapToGlobal(position))

        if action == remove_action:
            self.remove_friend()

    def show_pending_context_menu(self, position):
        item = self.pendingList.itemAt(position)
        if not item:
            return

        request_id = item.data(QtCore.Qt.UserRole)
        menu = QMenu()
        accept_action = menu.addAction(_("ui.friends_dialog.accept", "✅ قبول"))
        decline_action = menu.addAction(_("ui.friends_dialog.decline", "❌ رفض"))
        action = menu.exec_(self.pendingList.mapToGlobal(position))

        if action == accept_action:
            self.accept_friend_request(request_id)
        elif action == decline_action:
            self.decline_friend_request(request_id)

    def show_sent_context_menu(self, position):
        item = self.sentList.itemAt(position)
        if not item:
            return

        request_id = item.data(QtCore.Qt.UserRole)
        menu = QMenu()
        cancel_action = menu.addAction(_("ui.friends_dialog.cancel", "🚫 إلغاء الطلب"))
        action = menu.exec_(self.sentList.mapToGlobal(position))

        if action == cancel_action:
            self.cancel_friend_request(request_id)

    def accept_friend_request(self, request_id):
        try:
            api_client.set_token(self.access_token)
            response = api_client.post(f"/friends/accept_request/{request_id}")
            if response.get("message"):
                self.show_message(_("ui.friends.request_accepted", "تم قبول طلب الصداقة بنجاح."))
                self.load_data()
            else:
                error_msg = response.get("detail", _("ui.friends.accept_failed", "فشل في قبول طلب الصداقة."))
                self.show_message(error_msg, "Error")
        except Exception as e:
            self.show_message(str(e), "Error")

    def decline_friend_request(self, request_id):
        try:
            api_client.set_token(self.access_token)
            response = api_client.post(f"/friends/decline_request/{request_id}")
            if response.get("message"):
                self.show_message(_("ui.friends.request_declined", "تم رفض طلب الصداقة."))
                self.load_pending_requests()
            else:
                error_msg = response.get("detail", _("ui.friends.decline_failed", "فشل في رفض طلب الصداقة."))
                self.show_message(error_msg, "Error")
        except Exception as e:
            self.show_message(str(e), "Error")

    def cancel_friend_request(self, request_id):
        try:
            api_client.set_token(self.access_token)
            response = api_client.post(f"/friends/cancel_request/{request_id}")
            if response.get("message"):
                self.show_message(_("ui.friends.request_cancelled", "تم إلغاء طلب الصداقة."))
                self.load_sent_requests()
            else:
                error_msg = response.get("detail", _("ui.friends.cancel_failed", "فشل في إلغاء طلب الصداقة."))
                self.show_message(error_msg, "Error")
        except Exception as e:
            self.show_message(str(e), "Error")

    def search_users_dialog(self):
        search_term, ok = QInputDialog.getText(
            self,
            _("ui.friends_dialog.search_title", "بحث"),
            _("ui.friends_dialog.search_prompt", "أدخل اسم المستخدم للبحث:")
        )
        if ok and search_term:
            self.search_users(search_term)

    def search_users(self, search_term):
        try:
            response = requests.get(f"{API_BASE_URL}/friends/users/search?term={search_term}", headers=self.headers)

            if response.status_code == 200:
                users = response.json()
                if users:
                    dialog = UserSearchResultsDialog(users, self.access_token, self)
                    dialog.setWindowModality(QtCore.Qt.ApplicationModal)
                    dialog.user_added.connect(self.load_data)
                    dialog.exec_()
                else:
                    QMessageBox.information(self, _("ui.common.info", "معلومة"),
                                            _("ui.friends_dialog.no_users_found", "لا يوجد مستخدمين بهذا الاسم"))
            else:
                self.show_response_message(response,
                                           "",  # لا يوجد success msg
                                           _("ui.friends_dialog.search_error", "حدث خطأ أثناء البحث"))
        except Exception as e:
            log_error(f"[Search Users] {e}")
            QMessageBox.warning(self, "Error", str(e))

    def handle_pending_action(self, action_type):
        selected_items = self.pendingList.selectedItems()
        if not selected_items:
            self.show_message(_("ui.friends.select_request", "الرجاء اختيار طلب للتعامل معه."), "Warning")
            return

        request_id = selected_items[0].data(QtCore.Qt.UserRole)
        if action_type == "accept":
            self.accept_friend_request(request_id)
        else:
            self.decline_friend_request(request_id)

    def handle_sent_action(self):
        selected_items = self.sentList.selectedItems()
        if not selected_items:
            self.show_message(_("ui.friends.select_request", "الرجاء اختيار طلب للإلغاء."), "Warning")
            return

        request_id = selected_items[0].data(QtCore.Qt.UserRole)
        self.cancel_friend_request(request_id)
 