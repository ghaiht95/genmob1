import os
import json

class Translator:
    """فئة للتعامل مع ترجمة النصوص في التطبيق"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """الحصول على نسخة وحيدة من المترجم (نمط Singleton)"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """تهيئة المترجم"""
        # افتراضياً، نستخدم الإنجليزية
        self.current_language = "en"
        self.translations = {"en": {}, "ar": {}}
        self.load_translations()
    
    def load_translations(self):
        """تحميل ملفات الترجمات"""
        try:
            # البحث عن مسار ملفات الترجمة
            possible_paths = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'translations'),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'translations'),
                os.path.join(os.getcwd(), 'frontend', 'translations'),
                os.path.join(os.getcwd(), 'translations')
            ]
            
            translation_dir = None
            for path in possible_paths:
                if os.path.exists(path) and os.path.isdir(path):
                    translation_dir = path
                    print(f"Found translations directory at: {path}")
                    break
            
            if translation_dir:
                # تحميل الترجمات الإنجليزية
                en_file = os.path.join(translation_dir, 'en.json')
                if os.path.exists(en_file):
                    print(f"Loading English translation file: {en_file}")
                    with open(en_file, 'r', encoding='utf-8') as f:
                        self.translations["en"] = json.load(f)
                else:
                    print(f"English translation file not found at: {en_file}")
                
                # تحميل الترجمات العربية
                ar_file = os.path.join(translation_dir, 'ar.json')
                if os.path.exists(ar_file):
                    print(f"Loading Arabic translation file: {ar_file}")
                    with open(ar_file, 'r', encoding='utf-8') as f:
                        self.translations["ar"] = json.load(f)
                else:
                    print(f"Arabic translation file not found at: {ar_file}")
            else:
                print("Translation directory not found in any of the possible paths:")
                for path in possible_paths:
                    print(f"  - {path}")
        except Exception as e:
            print(f"Error loading translation files: {e}")
            import traceback
            traceback.print_exc()
    
    def set_language(self, language, force=False):
        """تغيير اللغة المستخدمة في التطبيق"""
        if language in ["en", "ar"]:
            print(f"تغيير اللغة إلى {language}")
            self.current_language = language
            return True
        else:
            print(f"اللغة غير مدعومة: {language}")
            return False
    
    def get_languages(self):
        """الحصول على قائمة اللغات المتاحة"""
        return ["en", "ar"]
    
    def translate(self, key, default="", **kwargs):
        """ترجمة نص بناءً على مفتاح الترجمة"""
        try:
            # تقسيم المفتاح إلى أجزاء (مثال: ui.main_window.title)
            parts = key.split('.')
            
            # البحث في شجرة الترجمة للغة الحالية
            value = self.translations[self.current_language]
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    print(f"مفتاح الترجمة غير موجود: {key} في اللغة {self.current_language} - استخدام القيمة الافتراضية: {default}")
                    return default
            
            # إذا لم تكن القيمة نصًا، أرجع القيمة الافتراضية
            if not isinstance(value, str):
                return default
            
            # استبدال المتغيرات في النص
            try:
                result = value.format(**kwargs)
                return result
            except Exception:
                return value
        except Exception as e:
            print(f"خطأ في الترجمة: {e}")
            return default

# اختصار للوصول السريع للمترجم
def _(key, default="", **kwargs):
    """دالة مختصرة للترجمة"""
    return Translator.get_instance().translate(key, default, **kwargs) 