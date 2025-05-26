# frontend/verify.py
import os
import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
from translator import Translator, _
from api_client import api_client

class VerifyApp(QtWidgets.QDialog):
    def __init__(self, email, mode="verify"):
        super().__init__()
        self.email = email
        self.mode = mode
        self.load_ui()
        self.setup_ui()

    def load_ui(self):
        ui_file = os.path.join(os.path.dirname(__file__), "ui", "verify_dialog.ui")
        uic.loadUi(ui_file, self)

    def setup_ui(self):
        self.setWindowTitle(_("ui.verify.title", "التحقق"))
        self.verify_btn.clicked.connect(self.verify_code)
        self.resend_btn.clicked.connect(self.resend_code)

    def verify_code(self):
        code = self.code_input.text().strip()
        if not code:
            self.show_message(_("ui.verify.enter_code", "الرجاء إدخال رمز التحقق."), "Warning")
            return

        try:
            if self.mode == "verify":
                response = api_client.post("/auth/verify", json={
                    "email": self.email,
                    "code": code
                })
            else:  # reset mode
                response = api_client.post("/auth/reset-password-verify", json={
                    "email": self.email,
                    "code": code
                })

            if response.status_code == 200:
                if self.mode == "verify":
                    self.show_message(_("ui.verify.success", "تم التحقق من البريد الإلكتروني بنجاح."))
                else:
                    self.show_message(_("ui.verify.reset_success", "تم التحقق من البريد الإلكتروني. يمكنك الآن إعادة تعيين كلمة المرور."))
                self.accept()
            else:
                error_msg = response.json().get("detail", _("ui.verify.failed", "فشل في التحقق من الرمز."))
                self.show_message(error_msg, "Error")
        except Exception as e:
            self.show_message(str(e), "Error")

    def resend_code(self):
        try:
            if self.mode == "verify":
                response = api_client.post("/auth/resend-verification", json={"email": self.email})
            else:  # reset mode
                response = api_client.post("/auth/reset-password-request", json={"email": self.email})

            if response.status_code == 200:
                self.show_message(_("ui.verify.resend_success", "تم إعادة إرسال رمز التحقق إلى بريدك الإلكتروني."))
            else:
                error_msg = response.json().get("detail", _("ui.verify.resend_failed", "فشل في إعادة إرسال رمز التحقق."))
                self.show_message(error_msg, "Error")
        except Exception as e:
            self.show_message(str(e), "Error")

    def show_message(self, message, title="Info"):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information if title == "Info" else QMessageBox.Warning)
        msg.setText(message)
        msg.setWindowTitle(_("ui.verify.info" if title == "Info" else "ui.verify.error", title))
        msg.exec_()
