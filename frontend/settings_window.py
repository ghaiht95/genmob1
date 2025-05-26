import os
import json
import pyaudio
import wave
import threading
import time
import subprocess
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import QTranslator, QLocale
from PyQt5 import uic
from translator import Translator, _
import logging

logger = logging.getLogger(__name__)

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super(SettingsWindow, self).__init__(parent)
        
        # تعديل طريقة تحميل ملف الواجهة
        try:
            # محاولة 1: استخدام المسار النسبي للمجلد الحالي
            current_dir = os.path.dirname(os.path.abspath(__file__))
            ui_file = os.path.join(current_dir, 'ui', 'settings_window.ui')
            
            if not os.path.exists(ui_file):
                # محاولة 2: مسار نسبي للمجلد الأساسي بدون frontend
                ui_file = os.path.join('ui', 'settings_window.ui')
                
                if not os.path.exists(ui_file):
                    # محاولة 3: مسار نسبي للمجلد الحالي
                    ui_file = os.path.join('.', 'ui', 'settings_window.ui')
                
            uic.loadUi(ui_file, self)
            print(f"تم تحميل ملف الواجهة بنجاح: {ui_file}")
        except Exception as e:
            print(f"خطأ في تحميل ملف الواجهة: {e}")
            raise
        
        self.settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
        self.settings = self.load_settings()
        self.translator = Translator.get_instance()
        
        # تهيئة PyAudio لقوائم الأجهزة
        try:
            self.audio = pyaudio.PyAudio()
            self.populate_audio_devices()
        except Exception as e:
            print(f"خطأ في تهيئة PyAudio: {e}")
            self.audio = None
            # تعطيل مجموعة الصوت في حالة عدم توفر PyAudio
            if hasattr(self, 'groupBox_audio'):
                self.groupBox_audio.setEnabled(False)
        
        # تحميل الإعدادات الحالية
        self.setup_ui()
        self.translate_ui()
        
        # ربط الأزرار والإشارات
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_cancel.clicked.connect(self.reject)
        if hasattr(self, 'btn_test_audio'):
            self.btn_test_audio.clicked.connect(self.test_audio)
        
    def populate_audio_devices(self):
        """تعبئة قوائم أجهزة الصوت المنسدلة"""
        if not self.audio:
            return
        
        # مسح القوائم
        self.combo_microphone.clear()
        self.combo_speaker.clear()
        
        # إضافة خيار "افتراضي" لكل قائمة
        self.combo_microphone.addItem("الجهاز الافتراضي", -1)
        self.combo_speaker.addItem("الجهاز الافتراضي", -1)
        
        # البحث عن أجهزة الإدخال والإخراج
        for i in range(self.audio.get_device_count()):
            try:
                dev_info = self.audio.get_device_info_by_index(i)
                
                # إضافة أجهزة الإدخال (المايكروفونات)
                if dev_info['maxInputChannels'] > 0:
                    self.combo_microphone.addItem(f"{dev_info['name']}", i)
                
                # إضافة أجهزة الإخراج (السماعات)
                if dev_info['maxOutputChannels'] > 0:
                    self.combo_speaker.addItem(f"{dev_info['name']}", i)
            except Exception as e:
                print(f"خطأ في الحصول على معلومات الجهاز {i}: {e}")
        
    def translate_ui(self):
        """ترجمة عناصر واجهة المستخدم"""
        self.setWindowTitle(_("ui.settings_window.title", "الإعدادات"))
        self.groupBox_language.setTitle(_("ui.settings_window.language", "اللغة"))
        self.radio_arabic.setText(_("ui.settings_window.arabic", "العربية"))
        self.radio_english.setText(_("ui.settings_window.english", "الإنجليزية"))
        self.groupBox_style.setTitle(_("ui.settings_window.style", "ستايل البرنامج"))
        
        # ترجمة عناصر القائمة المنسدلة للستايل
        self.combo_style.setItemText(0, _("ui.settings_window.default_style", "الستايل الافتراضي"))
        self.combo_style.setItemText(1, _("ui.settings_window.dark_style", "ستايل داكن"))
        self.combo_style.setItemText(2, _("ui.settings_window.light_style", "ستايل فاتح"))
        
        # ترجمة عناصر إعدادات الصوت
        if hasattr(self, 'groupBox_audio'):
            self.groupBox_audio.setTitle(_("ui.settings_window.audio_settings", "إعدادات الصوت"))
            self.label_mic.setText(_("ui.settings_window.microphone", "الميكروفون:"))
            self.label_speaker.setText(_("ui.settings_window.speaker", "السماعات:"))
            self.btn_test_audio.setText(_("ui.settings_window.test_audio", "اختبار الصوت"))
        
        # ترجمة الأزرار
        self.btn_save.setText(_("ui.settings_window.save", "حفظ"))
        self.btn_cancel.setText(_("ui.settings_window.cancel", "إلغاء"))
        
    def load_settings(self):
        """تحميل الإعدادات من الملف"""
        default_settings = {
            "language": "en",       # اللغة الافتراضية: الإنجليزية
            "style": "default",     # الستايل الافتراضي
            "audio": {              # إعدادات الصوت الافتراضية
                "input_device": -1,  # -1 تعني الجهاز الافتراضي
                "output_device": -1
            }
        }
        
        try:
            if os.path.exists(self.settings_file):
                try:
                    with open(self.settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                    
                    # التأكد من وجود قسم الصوت
                    if "audio" not in settings:
                        settings["audio"] = default_settings["audio"]
                    
                    return settings
                except Exception as e:
                    print(f"خطأ في قراءة ملف الإعدادات: {e}")
                    return default_settings
            else:
                # إنشاء ملف إعدادات افتراضي
                try:
                    with open(self.settings_file, 'w', encoding='utf-8') as f:
                        json.dump(default_settings, f, ensure_ascii=False, indent=4)
                    print(f"تم إنشاء ملف إعدادات جديد: {self.settings_file}")
                except Exception as e:
                    print(f"خطأ في إنشاء ملف الإعدادات: {e}")
                
                return default_settings
        except Exception as e:
            print(f"خطأ عام في التعامل مع ملف الإعدادات: {e}")
            return default_settings
    
    def setup_ui(self):
        """إعداد واجهة المستخدم بناءً على الإعدادات المحفوظة"""
        # إعداد اللغة
        current_language = self.settings.get("language", "en")
        if current_language == "ar":
            self.radio_arabic.setChecked(True)
            self.radio_english.setChecked(False)
        else:
            self.radio_english.setChecked(True)
            self.radio_arabic.setChecked(False)
        
        # إعداد الستايل
        style_index = 0  # افتراضي
        if self.settings.get("style") == "dark":
            style_index = 1
        elif self.settings.get("style") == "light":
            style_index = 2
        self.combo_style.setCurrentIndex(style_index)
        
        # إعداد أجهزة الصوت
        if hasattr(self, 'combo_microphone') and hasattr(self, 'combo_speaker'):
            # تحديد الميكروفون
            input_device = self.settings.get("audio", {}).get("input_device", -1)
            # تعيين فهرس القائمة المنسدلة المناسب
            input_index = 0  # الافتراضي هو الخيار الأول (الجهاز الافتراضي)
            for i in range(self.combo_microphone.count()):
                if self.combo_microphone.itemData(i) == input_device:
                    input_index = i
                    break
            self.combo_microphone.setCurrentIndex(input_index)
            
            # تحديد السماعات
            output_device = self.settings.get("audio", {}).get("output_device", -1)
            # تعيين فهرس القائمة المنسدلة المناسب
            output_index = 0  # الافتراضي هو الخيار الأول (الجهاز الافتراضي)
            for i in range(self.combo_speaker.count()):
                if self.combo_speaker.itemData(i) == output_device:
                    output_index = i
                    break
            self.combo_speaker.setCurrentIndex(output_index)
    
    def save_settings(self):
        """حفظ الإعدادات وتطبيقها"""
        # تحديد اللغة المختارة
        language = "en"
        if self.radio_arabic.isChecked():
            language = "ar"
        
        # تحديد الستايل
        style_index = self.combo_style.currentIndex()
        style = "default"
        if style_index == 1:
            style = "dark"
        elif style_index == 2:
            style = "light"
        
        # تحديد أجهزة الصوت
        audio_settings = {
            "input_device": -1,  # افتراضي
            "output_device": -1  # افتراضي
        }
        
        if hasattr(self, 'combo_microphone') and hasattr(self, 'combo_speaker'):
            # الحصول على فهرس الجهاز من البيانات المخزنة
            mic_idx = self.combo_microphone.currentIndex()
            spk_idx = self.combo_speaker.currentIndex()
            
            if mic_idx >= 0:
                audio_settings["input_device"] = self.combo_microphone.itemData(mic_idx)
            
            if spk_idx >= 0:
                audio_settings["output_device"] = self.combo_speaker.itemData(spk_idx)
        
        # حفظ الإعدادات
        self.settings = {
            "language": language,
            "style": style,
            "audio": audio_settings
        }
        
        try:
            print(f"محاولة حفظ الإعدادات في: {self.settings_file}")
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            
            # طبق اللغة الجديدة فوراً
            self.translator.set_language(language)
            
            # محاولة تحديث الترجمة فوراً
            self.translate_ui()
            
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText(_("ui.settings_window.success_message", "تم حفظ الإعدادات بنجاح"))
            msg.setInformativeText(_("ui.settings_window.restart_message", "يرجى إعادة تشغيل التطبيق لتطبيق التغييرات"))
            msg.setWindowTitle(_("ui.settings_window.success_title", "نجاح"))
            msg.exec_()
            
            self.accept()
        except Exception as e:
            print(f"خطأ عند حفظ الإعدادات: {e}")
            error_message = _("ui.settings_window.error_message", "حدث خطأ أثناء حفظ الإعدادات: {error}", error=str(e))
            QMessageBox.critical(self, _("ui.settings_window.error_title", "خطأ"), error_message)
    
    def test_audio(self):
        """اختبار إعدادات الصوت الحالية"""
        if not self.audio:
            QMessageBox.warning(self, "خطأ", "PyAudio غير متوفر، لا يمكن إجراء اختبار الصوت")
            return
        
        # الحصول على أجهزة الصوت المحددة
        mic_idx = self.combo_microphone.currentIndex()
        spk_idx = self.combo_speaker.currentIndex()
        
        input_device = self.combo_microphone.itemData(mic_idx)
        output_device = self.combo_speaker.itemData(spk_idx)
        
        # تنفيذ أداة اختبار الصوت
        try:
            # طريقة 1: تنفيذ مباشر للاختبار هنا
            QMessageBox.information(self, "اختبار الصوت", 
                        "سيتم تسجيل الصوت لمدة 3 ثوانٍ ثم تشغيله. تحدث الآن.")
            
            # معلمات الصوت
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 44100
            RECORD_SECONDS = 3
            
            frames = []
            
            # فتح تيار التسجيل
            try:
                stream_in = self.audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=None if input_device == -1 else input_device,
                    frames_per_buffer=CHUNK
                )
                
                print(f"جارٍ التسجيل باستخدام الجهاز: {input_device}")
                
                # تسجيل الصوت
                for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                    data = stream_in.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                
                # إغلاق تيار التسجيل
                stream_in.stop_stream()
                stream_in.close()
                
                # فتح تيار التشغيل
                stream_out = self.audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    output_device_index=None if output_device == -1 else output_device
                )
                
                print(f"جارٍ التشغيل باستخدام الجهاز: {output_device}")
                
                # تشغيل الصوت المسجل
                for frame in frames:
                    stream_out.write(frame)
                
                # إغلاق تيار التشغيل
                stream_out.stop_stream()
                stream_out.close()
                
                QMessageBox.information(self, "اختبار الصوت", "تم تسجيل وتشغيل الصوت. هل سمعت صوتك؟")
                
            except Exception as e:
                print(f"خطأ في اختبار الصوت: {e}")
                QMessageBox.critical(self, "خطأ", f"حدث خطأ أثناء اختبار الصوت: {e}")
            
            # طريقة 2 (بديلة): استدعاء audio_test.py
            # current_dir = os.path.dirname(os.path.abspath(__file__))
            # test_script = os.path.join(current_dir, 'audio_test.py')
            # 
            # cmd = [sys.executable, test_script]
            # if input_device != -1:
            #     cmd.extend(['--input', str(input_device)])
            # if output_device != -1:
            #     cmd.extend(['--output', str(output_device)])
            # 
            # subprocess.Popen(cmd)
            
        except Exception as e:
            print(f"خطأ في تنفيذ اختبار الصوت: {e}")
            QMessageBox.critical(self, "خطأ", f"حدث خطأ عند تنفيذ اختبار الصوت: {e}")
    
    @staticmethod
    def apply_settings(app):
        """تطبيق الإعدادات على التطبيق"""
        # البحث عن ملف الإعدادات في مسارات متعددة محتملة
        possible_paths = [
            os.path.join('frontend', 'settings.json'),
            os.path.join('.', 'settings.json'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
        ]
        
        settings_file = None
        for path in possible_paths:
            if os.path.exists(path):
                settings_file = path
                break
        
        # تهيئة المترجم
        translator = Translator.get_instance()
        
        if settings_file:
            try:
                print(f"تطبيق الإعدادات من: {settings_file}")
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # تطبيق اللغة المحددة
                language = settings.get("language", "en")
                translator.set_language(language)
                print(f"تم ضبط اللغة إلى: {language}")
                
                # تطبيق الستايل باستخدام ملفات QSS الخارجية
                style = settings.get("style", "default")
                current_dir = os.path.dirname(os.path.abspath(__file__))
                
                # تحديد مسارات محتملة لملفات الستايل
                style_paths = [
                    os.path.join(current_dir, 'styles', f'{style}.qss'),
                    os.path.join('frontend', 'styles', f'{style}.qss'),
                    os.path.join('styles', f'{style}.qss')
                ]
                
                style_file = None
                for path in style_paths:
                    if os.path.exists(path):
                        style_file = path
                        break
                
                if style_file:
                    try:
                        with open(style_file, 'r', encoding='utf-8') as f:
                            app.setStyleSheet(f.read())
                        print(f"تم تطبيق الستايل من الملف: {style_file}")
                    except Exception as e:
                        print(f"خطأ في قراءة ملف الستايل: {e}")
                else:
                    print(f"لم يتم العثور على ملف الستايل: {style}.qss")
                
            except Exception as e:
                print(f"خطأ في تطبيق الإعدادات: {e}")
    
    @staticmethod
    def get_audio_devices():
        """
        Get audio device settings from the saved settings file
        Returns a dictionary with input_device and output_device indices
        """
        try:
            if os.path.exists(os.path.join(os.path.expanduser("~"), ".voice_chat_settings.json")):
                with open(os.path.join(os.path.expanduser("~"), ".voice_chat_settings.json"), 'r') as f:
                    settings = json.load(f)
                    return {
                        'input_device': settings.get('input_device', -1),
                        'output_device': settings.get('output_device', -1)
                    }
        except Exception as e:
            logger.error(f"Error loading audio settings: {e}")
        
        # Default settings if file doesn't exist or error occurs
        return {
            'input_device': -1,  # -1 means use system default
            'output_device': -1
        }
    
    @staticmethod
    def save_audio_devices(input_device, output_device):
        """Save audio device settings to file"""
        try:
            settings = {
                'input_device': input_device,
                'output_device': output_device
            }
            with open(os.path.join(os.path.expanduser("~"), ".voice_chat_settings.json"), 'w') as f:
                json.dump(settings, f)
            return True
        except Exception as e:
            logger.error(f"Error saving audio settings: {e}")
            return False 