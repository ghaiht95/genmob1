# دليل إعداد WireGuard للتطبيق

## 🚨 مشكلة: "WireGuard غير موجود على نظامك"

إذا واجهت هذه الرسالة، فهذا يعني أن التطبيق لا يستطيع العثور على WireGuard على نظامك. إليك الحلول:

## 🔧 الحلول السريعة

### 1️⃣ الحل الأسرع: استخدام أداة الاكتشاف التلقائي
```bash
python find_wireguard.py
```
هذه الأداة ستبحث عن WireGuard تلقائياً وتنشئ ملف الإعداد المطلوب.

### 2️⃣ التثبيت الرسمي
1. حمّل WireGuard من: https://www.wireguard.com/install/
2. ثبّته باستخدام الإعدادات الافتراضية
3. أعد تشغيل التطبيق

### 3️⃣ النسخة المحمولة (إذا كانت لديك)
ضع ملف `wireguard.exe` في أحد هذه المواقع:
- `C:\Tools\WireGuard\wireguard.exe`
- `سطح المكتب\WireguardPortable\App\x64\wireguard.exe`
- `المستندات\WireGuard\wireguard.exe`

## 🛠️ الإعداد اليدوي

### الطريقة الأولى: متغير البيئة
1. اضغط `Win + R`
2. اكتب `sysdm.cpl` واضغط Enter
3. اذهب إلى `Advanced` → `Environment Variables`
4. أضف متغير جديد:
   - **الاسم**: `WIREGUARD_PATH`
   - **القيمة**: المسار الكامل لـ `wireguard.exe`

### الطريقة الثانية: ملف الإعداد
1. أنشئ ملف جديد باسم `wireguard_config.txt` في مجلد التطبيق
2. اكتب المسار الكامل لـ `wireguard.exe` في الملف
3. احفظ الملف

**مثال على محتوى الملف:**
```
C:\MyPrograms\WireGuard\wireguard.exe
```

## 📁 مسارات شائعة للبحث

### التثبيت الرسمي
- `C:\Program Files\WireGuard\wireguard.exe`
- `C:\Program Files (x86)\WireGuard\wireguard.exe`

### النسخ المحمولة
- `C:\Users\[USERNAME]\Desktop\fort\new\for\tools\WireguardPortable\App\x64\wireguard.exe`
- `C:\Tools\WireGuard\wireguard.exe`
- `C:\PortableApps\WireGuard\wireguard.exe`
- `سطح المكتب\WireGuard\wireguard.exe`

## 🔍 كيفية العثور على WireGuard يدوياً

### 1. البحث في File Explorer
1. افتح File Explorer
2. اذهب إلى القرص C:
3. ابحث عن "wireguard.exe"

### 2. استخدام Command Prompt
```cmd
where wireguard.exe
```

### 3. البحث في Registry
1. اضغط `Win + R`
2. اكتب `regedit`
3. ابحث عن "WireGuard"

## ❗ استكشاف الأخطاء

### المشكلة: "WireGuard executable not found"
**الحل**: تأكد أن المسار صحيح ويحتوي على `wireguard.exe`

### المشكلة: "Custom WireGuard path exists but not working"
**الحل**: 
1. تأكد أن الملف هو النسخة الصحيحة من WireGuard
2. جرب تشغيل الملف يدوياً للتأكد من عمله

### المشكلة: "Administrator privileges required"
**الحل**: 
1. أغلق التطبيق
2. انقر بالزر الأيمن على أيقونة التطبيق
3. اختر "Run as administrator"

## 🧪 اختبار الإعداد

بعد تطبيق أي من الحلول أعلاه، أعد تشغيل التطبيق. يجب أن ترى رسالة:
```
✅ Found WireGuard at: [المسار]
```

## 📞 الدعم الفني

إذا لم تنجح أي من هذه الحلول:
1. تأكد أن لديك صلاحيات المدير
2. تحقق من إعدادات مكافح الفيروسات
3. جرب إعادة تشغيل النظام

## 📋 ملاحظات مهمة

- **صلاحيات المدير مطلوبة**: WireGuard يحتاج صلاحيات عالية للعمل
- **مكافح الفيروسات**: قد يحجب بعض برامج مكافحة الفيروسات WireGuard
- **التطبيق سيعمل بدون VPN**: لكن لن تتمكن من الاتصال بخوادم الألعاب

## 🎮 بعد حل المشكلة

بمجرد العثور على WireGuard وإعداده:
1. ستتمكن من الانضمام للغرف
2. سيتم إنشاء اتصال VPN تلقائياً
3. ستتمكن من الاتصال بخوادم الألعاب الخاصة

---

**نصيحة**: احتفظ بنسخة احتياطية من ملف `wireguard_config.txt` للمرات القادمة! 