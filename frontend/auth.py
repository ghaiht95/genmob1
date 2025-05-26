import os
import requests
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QSettings, QThread, pyqtSignal
import subprocess
from verify import VerifyApp
from main_app import MainApp
from translator import Translator, _
from api_client import api_client
import re

from PyQt5.QtCore import Qt


API_BASE_URL = "http://31.220.80.192:8000"  # Updated port for FastAPI

class VPNSetupThread(QThread):
    setup_finished = pyqtSignal(bool, str)  # إشارة لإعلام انتهاء التثبيت (نجاح/فشل، رسالة)
    
    def __init__(self):
        super().__init__()
        # إعداد المسارات
        self.tools_path = os.path.join(os.getcwd(), "tools")
        self.inf_path = os.path.join(self.tools_path, "Neo6_x64_VPN.inf")
        self.devcon_path = os.path.join(self.tools_path, "devcon.exe")
        self.target_hwid = "NeoAdapter_VPN"
        self.install_hwid = "NeoAdapter_VPN"  # هذا يُستخدم فقط عند التثبيت
        
    def run(self):
        try:
            # وظيفة لتشغيل أوامر وإرجاع الإخراج
            def run_cmd(command):
                result = subprocess.run(command, capture_output=True, text=True, shell=True)
                return result.stdout.strip()

            # التحقق من وجود الجهاز عبر HWID داخل الأجهزة المثبتة
            print("Checking for existing device (by HWID)...")
            hwids_output = run_cmd(f'"{self.devcon_path}" hwids *')

            if self.target_hwid.lower() in hwids_output.lower():
                print(f"Device with HWID '{self.target_hwid}' is already installed.")
            else:
                print("Device not found. Installing...")

                print("Adding driver to driver store...")
                subprocess.run(["pnputil", "/add-driver", self.inf_path, "/install"], shell=True)

                print("Installing device using devcon...")
                subprocess.run([self.devcon_path, "install", self.inf_path, self.install_hwid], shell=True)

            # تفعيل الجهاز (حتى لو كان مثبّتًا من قبل)
            print("Ensuring device is enabled...")
            enable_output = run_cmd(f'"{self.devcon_path}" enable {self.target_hwid}')
            print(enable_output)

            print("VPN adapter setup completed successfully.")
            self.setup_finished.emit(True, "VPN adapter setup completed.")
        except Exception as e:
            print(f"Error setting up VPN adapter: {e}")
            self.setup_finished.emit(False, f"Error setting up VPN adapter: {e}")

class AuthApp(QtWidgets.QMainWindow):
    def __init__(self):
        super(AuthApp, self).__init__()
        file_path = os.path.join(os.getcwd(), 'ui', 'auth_window.ui')
        uic.loadUi(file_path, self)

        self.settings = QSettings("YourCompany", "YourApp")

        # ضبط RTL
        self.group_login.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.group_register.setLayoutDirection(QtCore.Qt.RightToLeft)

        # ترجمة النصوص
        self.translate_ui()

        # ربط الأزرار
        self.btn_login.clicked.connect(self.login)
        self.btn_forgot.clicked.connect(self.forgot_password)
        self.btn_register.clicked.connect(self.register)

        self.load_saved_credentials()

    def translate_ui(self):
        # تحديد اللغة الحالية
        lang = Translator.get_instance().current_language

        # تحديد الاتجاه بناءً على اللغة
        direction = Qt.RightToLeft if lang == "ar" else Qt.LeftToRight
        self.setLayoutDirection(direction)
        self.group_login.setLayoutDirection(direction)
        self.group_register.setLayoutDirection(direction)
        self.label_title.setText(_("ui.auth_window.label_title", "مرحباً بك في التطبيق"))


        # الترجمة العادية
        self.setWindowTitle(_("ui.auth_window.title", "تسجيل الدخول / التسجيل"))
        self.group_login.setTitle(_("ui.auth_window.login_group", "تسجيل الدخول"))
        self.group_register.setTitle(_("ui.auth_window.register_group", "إنشاء حساب"))

        self.label_login_email.setText(_("ui.auth_window.email_label", "البريد الإلكتروني:"))
        self.label_login_password.setText(_("ui.auth_window.password_label", "كلمة المرور:"))
        self.remember_me.setText(_("ui.auth_window.remember_me", "تذكرني"))
        self.btn_login.setText(_("ui.auth_window.login_button", "تسجيل الدخول"))
        self.btn_forgot.setText(_("ui.auth_window.forgot_button", "نسيت كلمة المرور؟"))

        self.label_reg_username.setText(_("ui.auth_window.username_label", "اسم المستخدم:"))
        self.label_reg_email.setText(_("ui.auth_window.email_label", "البريد الإلكتروني:"))
        self.label_reg_password.setText(_("ui.auth_window.password_label", "كلمة المرور:"))
        self.label_reg_confirm.setText(_("ui.auth_window.confirm_password_label", "تأكيد كلمة المرور:"))
        self.btn_register.setText(_("ui.auth_window.register_button", "تسجيل"))

        # Placeholder
        self.reg_username.setPlaceholderText(_("ui.auth_window.username_label", "اسم المستخدم"))
        self.reg_email.setPlaceholderText(_("ui.auth_window.email_label", "البريد الإلكتروني"))
        self.reg_password.setPlaceholderText(_("ui.auth_window.password_label", "كلمة المرور"))  
        self.reg_confirm.setPlaceholderText(_("ui.auth_window.confirm_password_label", "تأكيد كلمة المرور"))

    def load_saved_credentials(self):
        email = self.settings.value("email", "")
        password = self.settings.value("password", "")
        remember = self.settings.value("remember_me", False, type=bool)

        if email:
            self.login_email.setText(email)
        if password and remember:
            self.login_password.setText(password)
            self.remember_me.setChecked(True)

    def save_credentials(self, email, password, remember):
        if remember:
            self.settings.setValue("email", email)
            self.settings.setValue("password", password)
            self.settings.setValue("remember_me", True)
        else:
            self.settings.clear()

    def show_message(self, message, title="Info"):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information if title == "Info" else QMessageBox.Warning)
        msg.setText(message)
        msg.setWindowTitle(_("ui.auth_window.info" if title == "Info" else "ui.auth_window.error", title))
        msg.exec_()

    def login(self):
        email = self.login_email.text().strip()
        password = self.login_password.text().strip()
        remember = self.remember_me.isChecked()

        if not email or not password:
            self.show_message(_("ui.auth_window.enter_email_password", "يرجى إدخال البريد وكلمة المرور."), "Error")
            return

        try:
            # Using form-encoded data for OAuth2 as required by FastAPI
            response = api_client.post("/auth/token", data={
                "username": email,  # Using email as username for login
                "password": password
            })
            # If we get here, login was successful
            access_token = response.get("access_token")
            if access_token:
                api_client.set_token(access_token)
                self.show_message(_("ui.auth_window.login_success", "تم تسجيل الدخول بنجاح."))
                # جلب بيانات المستخدم بعد تسجيل الدخول
                try:
                    user_data = api_client.get("/auth/me")
                    user_data["access_token"] = access_token
                    self.main_window = MainApp(user_data=user_data)
                    self.main_window.show()
                    self.close()
                except Exception as e:
                    self.show_message(_("ui.auth_window.user_fetch_error", "تم تسجيل الدخول لكن فشل في جلب بيانات المستخدم."), "Error")
            else:
                self.show_message(_("ui.auth_window.login_error", "فشل تسجيل الدخول: لم يتم استلام التوكن."), "Error")
        except Exception as e:
            self.show_message(_("ui.auth_window.connection_error", "خطأ في الاتصال: {error}", error=str(e)), "Error")

    def register(self):
        username = self.reg_username.text().strip()
        email = self.reg_email.text().strip()
        password = self.reg_password.text().strip()
        confirm = self.reg_confirm.text().strip()

        if not username or not email or not password or not confirm:
            self.show_message(_("ui.auth_window.fill_all_fields", "يرجى ملء جميع الحقول."), "Error")
            return

        if password != confirm:
            self.show_message(_("ui.auth_window.passwords_not_match", "كلمات المرور غير متطابقة."), "Error")
            return

        try:
            response = api_client.post("/auth/register", json={
                "username": username,
                "email": email,
                "password": password
            })
            # If we get here, registration was successful
            self.show_message(_("ui.auth_window.verification_sent", "تم إنشاء الحساب بنجاح، تم إرسال رمز التحقق إلى بريدك."))
            self.verify_window = VerifyApp(email=email)
            self.verify_window.exec_()
        except Exception as e:
            error_msg = str(e)
            # إذا كان الاستثناء من نوع requests.exceptions.HTTPError وفيه response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("detail", error_msg)
                except Exception:
                    pass
            if "Username already registered" in error_msg:
                self.show_message(_("ui.auth_window.register_error", "اسم المستخدم مسجل مسبقاً."), "Error")
            elif "Email already registered" in error_msg:
                self.show_message(_("ui.auth_window.register_error", "البريد الإلكتروني مسجل مسبقاً."), "Error")
            else:
                self.show_message(_(
                    "ui.auth_window.register_error",
                    "{error}",
                    error=error_msg
                ), "Error")

    def forgot_password(self):
        email = self.login_email.text().strip()
        if not email:
            self.show_message(_("ui.auth_window.enter_email", "الرجاء إدخال بريدك الإلكتروني."), "Error")
            return
        # Email format validation
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, email):
            self.show_message(_("ui.auth_window.invalid_email", "يرجى إدخال بريد إلكتروني صالح."), "Error")
            return
        try:
            response = api_client.post("/auth/reset-password-request", json={"email": email})
            self.show_message(_("ui.auth_window.reset_sent", "تم إرسال رمز إعادة التعيين إلى بريدك."))
            self.verify_window = VerifyApp(email=email, mode="reset")
            self.verify_window.exec_()
        except Exception as e:
            self.show_message(_("ui.auth_window.connection_error", "خطأ في الاتصال: {error}", error=str(e)), "Error")

    def on_vpn_setup_finished(self, success, message):
        """معالجة نتيجة تثبيت محول VPN"""
        if not success:
            print(f"VPN adapter setup warning: {message}")
            # لا نريد إظهار رسالة للمستخدم إلا في حالة خطأ حرج
