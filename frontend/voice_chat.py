import logging
import os
import time
import threading
import pyaudio
import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal

from settings_window import SettingsWindow

# إعداد السجلات
logger = logging.getLogger(__name__)

# -------- فئة VoiceChat للدردشة الصوتية --------
class VoiceChat(QtCore.QObject):
    new_audio_signal = pyqtSignal(bytes, str)  # إشارة لتلقي صوت جديد (البيانات، اسم المستخدم)
    
    def __init__(self, socket, room_id, username):
        super().__init__()
        self.socket = socket
        self.room_id = room_id
        self.username = username
        self.is_muted = True
        self.is_connected = False
        self.is_recording = False
        self.stream_in = None
        self.stream_out = None
        self.audio = None
        
        # إعدادات الصوت - تم تقليل الجودة لتحسين الأداء
        self.CHUNK = 512  # تم تقليله من 1024 للحصول على حزم صوت أصغر
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 22050  # تم تقليله من 44100 لتقليل حجم البيانات
        
        # الحصول على أجهزة الصوت المُخزنة في الإعدادات
        self.audio_settings = SettingsWindow.get_audio_devices()
        self.input_device = self.audio_settings.get('input_device', -1)
        self.output_device = self.audio_settings.get('output_device', -1)
        
        # طباعة محاولة تهيئة PyAudio للتشخيص
        try:
            print("Initializing PyAudio for diagnosis...")
            print(f"Using audio settings - Input: {self.input_device}, Output: {self.output_device}")
            self.audio = pyaudio.PyAudio()
            print(f"PyAudio initialized successfully")
            
            # طباعة معلومات عن الأجهزة المتاحة
            print(f"Audio devices available: {self.audio.get_device_count()}")
            for i in range(self.audio.get_device_count()):
                try:
                    dev_info = self.audio.get_device_info_by_index(i)
                    print(f"Device {i}: {dev_info['name']}")
                    print(f"  Max Input Channels: {dev_info['maxInputChannels']}")
                    print(f"  Max Output Channels: {dev_info['maxOutputChannels']}")
                    print(f"  Default Sample Rate: {dev_info['defaultSampleRate']}")
                except Exception as e:
                    print(f"Error getting device info for device {i}: {e}")
            
            # تهيئة تيارات الصوت
            self._init_streams()
            
        except Exception as e:
            print(f"Error in PyAudio initialization: {e}")
            import traceback
            traceback.print_exc()
            self.audio = None
        
        # ربط إشارات Socket.IO للصوت
        self.socket.on('voice_data', self.on_voice_data)
    
    def _init_streams(self):
        """تهيئة تيارات الصوت للتسجيل والتشغيل"""
        if not self.audio:
            print("❌ PyAudio غير متاح، لا يمكن إنشاء تيارات الصوت")
            return
            
        # إغلاق أي تيارات مفتوحة
        if self.stream_in:
            self.stream_in.close()
        if self.stream_out:
            self.stream_out.close()
            
        # طباعة معلومات عن الميكروفون المختار
        print(f"ℹ️ محاولة استخدام الميكروفون {self.input_device}")
        
        # تهيئة تيار الإدخال (التسجيل)
        self.stream_in = None  # تأكد من أنه لا يوجد تيار إدخال نشط
        
        # قائمة الميكروفونات للمحاولة
        mic_to_try = []
        
        # أولاً الميكروفون المحدد في الإعدادات إذا كان موجوداً
        if self.input_device != -1:
            mic_to_try.append((self.input_device, "المحدد في الإعدادات"))
        
        # ثم ميكروفون النظام الافتراضي
        mic_to_try.append((None, "الافتراضي"))
        
        # ثم جرب كل الميكروفونات المتاحة إذا فشلت المحاولات السابقة
        for i in range(self.audio.get_device_count()):
            try:
                dev_info = self.audio.get_device_info_by_index(i)
                if dev_info['maxInputChannels'] > 0:
                    mic_to_try.append((i, f"{dev_info['name']}"))
            except Exception as e:
                print(f"⚠️ لا يمكن الحصول على معلومات الجهاز {i}: {e}")
        
        # جرب الميكروفونات واحدًا تلو الآخر
        successful_mic = False
        for mic_index, mic_name in mic_to_try:
            try:
                print(f"🎤 محاولة تهيئة الميكروفون {mic_index}: {mic_name}")
                stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    input_device_index=mic_index,
                    frames_per_buffer=self.CHUNK
                )
                
                # اختبار التسجيل سريعًا
                print(f"📝 اختبار قراءة البيانات من الميكروفون {mic_index}")
                try:
                    data = stream.read(self.CHUNK, exception_on_overflow=False)
                    print(f"✅ نجح اختبار الميكروفون {mic_index}: تم تلقي {len(data)} بايت")
                    self.stream_in = stream
                    successful_mic = True
                    # حفظ الميكروفون الذي نجح لاستخدامه لاحقًا
                    self.input_device = mic_index
                    print(f"🎯 تم تعيين الميكروفون {mic_index} كجهاز إدخال فعال")
                    break
                except Exception as e:
                    print(f"❌ فشل اختبار الميكروفون {mic_index}: {e}")
                    stream.close()
                    
            except Exception as e:
                print(f"❌ فشل تهيئة الميكروفون {mic_index}: {e}")
                
        if not successful_mic:
            print("⛔ فشلت جميع محاولات تهيئة الميكروفون!")
        else:
            print(f"✅ تم تهيئة تيار الإدخال بنجاح باستخدام الميكروفون {self.input_device}")
            
        # تهيئة تيار الإخراج (التشغيل)
        try:
            output_device_idx = None if self.output_device == -1 else self.output_device
            self.stream_out = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                output_device_index=output_device_idx,
                frames_per_buffer=self.CHUNK
            )
            print(f"✅ تم تهيئة تيار الإخراج بنجاح باستخدام الجهاز: {output_device_idx}")
        except Exception as e:
            print(f"❌ خطأ في تهيئة تيار الإخراج: {e}")
            # محاولة مرة أخرى بالجهاز الافتراضي إذا فشلت باستخدام الجهاز المحدد
            if self.output_device != -1:
                try:
                    print("🔄 محاولة باستخدام جهاز الإخراج الافتراضي")
                    self.stream_out = self.audio.open(
                        format=self.FORMAT,
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        output=True,
                        frames_per_buffer=self.CHUNK
                    )
                    print("✅ تم تهيئة تيار الإخراج باستخدام الجهاز الافتراضي")
                except Exception as e2:
                    print(f"❌ فشل تهيئة تيار الإخراج باستخدام الجهاز الافتراضي: {e2}")
                    self.stream_out = None
            else:
                self.stream_out = None
    
    def start_voice(self):
        """بدء اتصال الصوت"""
        if self.is_connected or not self.audio:
            return
            
        self.is_connected = True
        
        # بدء التسجيل إذا لم يكن مكتوماً
        if not self.is_muted:
            self.start_recording()
            
        print("Voice chat initialized")
    
    def stop_voice(self):
        """إيقاف اتصال الصوت"""
        if not self.is_connected:
            return
            
        self.stop_recording()
        
        # إغلاق تيارات الصوت
        if self.stream_in:
            self.stream_in.close()
            self.stream_in = None
        if self.stream_out:
            self.stream_out.close()
            self.stream_out = None
        
        # إنهاء PyAudio
        if self.audio:
            self.audio.terminate()
            self.audio = None
            
        self.is_connected = False
        print("Voice chat stopped")
    
    def toggle_mute(self):
        """تبديل حالة كتم الميكروفون"""
        print(f"Toggling mute: {self.is_muted} -> {not self.is_muted}")
        self.is_muted = not self.is_muted
        
        if self.is_connected:
            if self.is_muted:
                self.stop_recording()
            else:
                self.start_recording()
                
        return self.is_muted
    
    def start_recording(self):
        """بدء تسجيل الصوت وإرساله"""
        if self.is_recording or not self.is_connected or self.is_muted or not self.stream_in:
            return
            
        self.is_recording = True
        
        # إنشاء خيط لتسجيل الصوت وإرساله
        self.recording_thread = threading.Thread(target=self._record_and_send)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        print("Started voice recording")
    
    def _record_and_send(self):
        """تسجيل وإرسال الصوت في خيط منفصل"""
        try:
            print("=== بدء تسجيل وإرسال الصوت ===")
            while self.is_recording and self.stream_in and self.is_connected and not self.is_muted:
                try:
                    # قراءة الصوت من الميكروفون
                    audio_data = self.stream_in.read(self.CHUNK, exception_on_overflow=False)
                    
                    # طباعة تشخيصية لحجم البيانات
                    print(f"📤 تسجيل صوت: {len(audio_data)} بايت")
                    
                    # إرسال البيانات عبر Socket.IO
                    if self.socket.connected:
                        self.socket.emit('voice_data', {
                            'room_id': self.room_id,
                            'username': self.username,
                            'data': audio_data
                        })
                        print(f"✅ تم إرسال بيانات صوتية بنجاح: {len(audio_data)} بايت")
                    else:
                        print("❌ Socket.IO غير متصل، لا يمكن إرسال الصوت")
                except Exception as e:
                    print(f"❌ خطأ في حلقة التسجيل: {e}")
                    time.sleep(0.1)  # تأخير صغير لتجنب استهلاك CPU
        except Exception as e:
            print(f"❌ خطأ في خيط التسجيل: {e}")
            import traceback
            traceback.print_exc()
        
        self.is_recording = False
        print("توقف خيط التسجيل")
    
    def stop_recording(self):
        """إيقاف تسجيل الصوت"""
        if not self.is_recording:
            return
            
        self.is_recording = False
        print("Stopped voice recording")
    
    def on_voice_data(self, data):
        """استقبال بيانات صوتية من المستخدمين الآخرين"""
        try:
            username = data.get('username', 'Unknown')
            audio_data = data.get('data')
            
            print(f"📥 استلام بيانات صوتية من {username}")
            print(f"   حجم البيانات: {len(audio_data) if audio_data else 'None'} بايت")
            print(f"   نوع البيانات: {type(audio_data)}")
            
            # طباعة أول عدة بايتات للفحص (مختصر)
            if audio_data and len(audio_data) > 0:
                print(f"   أول 10 بايت: {audio_data[:10]}")
                
                # تحويل البيانات إلى مصفوفة للتحقق من وجود إشارة صوتية
                try:
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    audio_level = np.abs(audio_np).mean()
                    print(f"   مستوى الصوت: {audio_level:.2f}")
                except Exception as e:
                    print(f"   ⚠️ لا يمكن تحليل البيانات الصوتية: {e}")
            
            # IMPORTANT: تعليق هذا الفحص مؤقتًا للتشخيص
            # تجاهل البيانات الصوتية الخاصة بنا
            # if username == self.username:
            #     print(f"   ⏭️ تجاهل البيانات الصوتية الخاصة بنا من {username}")
            #     return
            
            # تشغيل الصوت مباشرة
            if audio_data:
                print(f"   🔊 محاولة تشغيل {len(audio_data)} بايت من البيانات الصوتية")
                self._play_audio(audio_data)
            else:
                print("   ⚠️ لا توجد بيانات صوتية للتشغيل")
            
        except Exception as e:
            print(f"❌ خطأ في معالجة البيانات الصوتية: {e}")
            import traceback
            traceback.print_exc()
    
    def _play_audio(self, audio_data):
        """تشغيل الصوت المستلم"""
        if not audio_data:
            print("❌ لا توجد بيانات صوتية للتشغيل")
            return
            
        if not self.stream_out:
            print("❌ دفق الإخراج غير متاح للتشغيل")
            print("🔄 محاولة إعادة تهيئة دفق الإخراج...")
            try:
                # إعادة تهيئة PyAudio إذا لزم الأمر
                if not self.audio:
                    print("🔄 إعادة تهيئة PyAudio...")
                    self.audio = pyaudio.PyAudio()
                
                # محاولة إنشاء دفق إخراج جديد
                self.stream_out = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    output=True,
                    frames_per_buffer=self.CHUNK
                )
                print("✅ تم إنشاء دفق إخراج جديد")
            except Exception as e:
                print(f"❌ فشل إنشاء دفق الإخراج: {e}")
                return
            
        if not self.is_connected:
            print("❌ الدردشة الصوتية غير متصلة")
            return
            
        try:
            print(f"🔊 تشغيل {len(audio_data)} بايت من البيانات الصوتية")
            
            # التحقق من حالة دفق الإخراج
            if not self.stream_out.is_active():
                print("⚠️ دفق الإخراج غير نشط، محاولة إعادة فتحه...")
                self.stream_out.close()
                self.stream_out = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    output=True,
                    frames_per_buffer=self.CHUNK
                )
                print("✅ تمت إعادة فتح دفق الإخراج")
            
            # محاولة كتابة البيانات إلى دفق الإخراج
            self.stream_out.write(audio_data)
            print("✅ تم تشغيل الصوت بنجاح")
        except Exception as e:
            print(f"❌ خطأ في تشغيل الصوت: {e}")
            
            # إعادة تهيئة تيار الإخراج في حالة الخطأ
            try:
                print("🔄 محاولة إعادة تهيئة دفق الإخراج...")
                if self.stream_out:
                    self.stream_out.close()
                
                self.stream_out = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    output=True,
                    frames_per_buffer=self.CHUNK
                )
                print("✅ تمت إعادة تهيئة دفق الإخراج بنجاح")
                
                # محاولة تشغيل الصوت مرة أخرى
                print("🔄 محاولة تشغيل الصوت مرة أخرى...")
                self.stream_out.write(audio_data)
                print("✅ نجحت المحاولة الثانية لتشغيل الصوت")
            except Exception as e2:
                print(f"❌ فشلت إعادة تهيئة إخراج الصوت: {e2}")
                import traceback
                traceback.print_exc() 