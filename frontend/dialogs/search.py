from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QDialog, QMessageBox, QListWidgetItem
import requests
from translator import _
from dotenv import load_dotenv
import os


load_dotenv()

# 🟡 قراءة عنوان الـ API من المتغير البيئي
API_BASE_URL = os.getenv("API_BASE_URL")


class UserSearchResultsDialog(QDialog):
    user_added = QtCore.pyqtSignal()

    def __init__(self, users, access_token, parent=None, current_user_id=None):
        super().__init__(parent)
        self.setWindowTitle(_("ui.search_results.title", "نتائج البحث"))
        self.setMinimumSize(400, 300)

        self.users = users
        self.access_token = access_token
        self.current_user_id = current_user_id
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

        layout = QtWidgets.QVBoxLayout(self)

        if not users:
            layout.addWidget(QtWidgets.QLabel(_("ui.search_results.no_results", "لا يوجد مستخدمين مطابقين")))
            return

        self.usersList = QtWidgets.QListWidget()
        for user in users:
            if user["id"] == self.current_user_id:
                continue  # تجاهل المستخدم نفسه
            item = QListWidgetItem(user["username"])
            item.setData(QtCore.Qt.UserRole, user["id"])
            self.usersList.addItem(item)

        layout.addWidget(self.usersList)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton(_("ui.search_results.add_friend", "إضافة كصديق"))
        self.btn_cancel = QtWidgets.QPushButton(_("ui.search_results.cancel", "إلغاء"))

        self.btn_add.setEnabled(False)  # الزر غير مفعل إلا بعد التحديد

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_add.clicked.connect(self.add_selected_user)
        self.btn_cancel.clicked.connect(self.reject)
        self.usersList.itemSelectionChanged.connect(self.toggle_add_button)

    def toggle_add_button(self):
        self.btn_add.setEnabled(bool(self.usersList.selectedItems()))

    def add_selected_user(self):
        selected_items = self.usersList.selectedItems()
        if not selected_items:
            QMessageBox.information(self, _("ui.messages.info", "معلومة"),
                                    _("ui.search_results.select_user", "الرجاء تحديد مستخدم"))
            return

        user_item = selected_items[0]
        user_id = user_item.data(QtCore.Qt.UserRole)
        username = user_item.text()

        try:
            response = self.send_friend_request(user_id)

            if response.status_code == 200:
                QMessageBox.information(self, _("ui.messages.info", "تم"),
                                        _( "ui.search_results.request_sent",
                                           f"تم إرسال الطلب إلى {username}"))
                self.user_added.emit()
                self.accept()
            else:
                msg = _("ui.search_results.request_failed", "فشل في إرسال الطلب.")
                try:
                    msg = response.json().get("detail", msg)
                except:
                    pass
                QMessageBox.warning(self, _("ui.messages.error", "خطأ"), msg)

        except Exception as e:
            QMessageBox.warning(self, _("ui.messages.error", "خطأ"), f"Error: {e}")

    def send_friend_request(self, user_id):
        return requests.post(
            f"{API_BASE_URL}/friends/request",
            json={"user_id": user_id},
            headers=self.headers,
            timeout=10
        )
