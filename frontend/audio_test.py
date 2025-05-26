#!/usr/bin/env python3
"""
أداة اختبار الصوت المستقلة
---------------------------
هذه الأداة تساعد في التحقق من عمل مكتبة PyAudio وأجهزة الصوت بشكل صحيح.
قم بتشغيل هذا الملف مباشرة للتحقق من إعدادات الصوت وتشخيص المشاكل.
"""

import sys
import time
import traceback
import argparse

try:
    import pyaudio
    import numpy as np
except ImportError as e:
    print(f"خطأ: لم يتم العثور على المكتبات المطلوبة. {e}")
    print("الرجاء تثبيت المكتبات المطلوبة باستخدام:")
    print("pip install pyaudio numpy")
    sys.exit(1)

def print_audio_devices():
    """طباعة معلومات حول أجهزة الصوت المتاحة"""
    try:
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        
        print(f"\n=== معلومات أجهزة الصوت المتاحة ===")
        print(f"عدد الأجهزة: {device_count}")
        
        for i in range(device_count):
            try:
                dev_info = p.get_device_info_by_index(i)
                print(f"\nجهاز {i}: {dev_info['name']}")
                print(f"  قنوات الإدخال: {dev_info['maxInputChannels']}")
                print(f"  قنوات الإخراج: {dev_info['maxOutputChannels']}")
                print(f"  معدل العينات الافتراضي: {dev_info['defaultSampleRate']}")
                print(f"  جهاز الإدخال الافتراضي: {dev_info['index'] == p.get_default_input_device_info()['index']}")
                print(f"  جهاز الإخراج الافتراضي: {dev_info['index'] == p.get_default_output_device_info()['index']}")
            except Exception as e:
                print(f"  خطأ في الحصول على معلومات الجهاز {i}: {e}")
        
        print("\n=== معلومات الأجهزة الافتراضية ===")
        try:
            default_input = p.get_default_input_device_info()
            print(f"جهاز الإدخال الافتراضي: {default_input['index']} - {default_input['name']}")
        except Exception as e:
            print(f"خطأ في الحصول على جهاز الإدخال الافتراضي: {e}")
            
        try:
            default_output = p.get_default_output_device_info()
            print(f"جهاز الإخراج الافتراضي: {default_output['index']} - {default_output['name']}")
        except Exception as e:
            print(f"خطأ في الحصول على جهاز الإخراج الافتراضي: {e}")
            
        p.terminate()
    except Exception as e:
        print(f"خطأ في طباعة معلومات الأجهزة: {e}")
        traceback.print_exc()

def test_recording(seconds=3, input_device=None):
    """اختبار تسجيل الصوت لمدة محددة واستعادة البيانات"""
    frames = []
    p = None
    stream = None
    
    try:
        print(f"\n=== اختبار تسجيل الصوت ({seconds} ثواني) ===")
        
        # إعداد معلمات التسجيل
        p = pyaudio.PyAudio()
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        
        # تحديد جهاز الإدخال
        if input_device is not None:
            try:
                device_info = p.get_device_info_by_index(input_device)
                print(f"استخدام جهاز الإدخال: {input_device} - {device_info['name']}")
            except:
                print(f"تحذير: لم يتم العثور على جهاز الإدخال {input_device}. استخدام الجهاز الافتراضي.")
                input_device = None
        
        # إنشاء دفق التسجيل
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=input_device,
            frames_per_buffer=CHUNK
        )
        
        print("تم فتح دفق التسجيل بنجاح")
        print(f"جاري التسجيل لمدة {seconds} ثواني... (تحدث الآن)")
        
        # تسجيل البيانات
        for i in range(0, int(RATE / CHUNK * seconds)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            # طباعة تقدم التسجيل كل ثانية
            if i % int(RATE / CHUNK) == 0:
                seconds_recorded = i / (RATE / CHUNK)
                print(f"  تم التسجيل: {seconds_recorded:.1f} ثانية")
        
        print("تم الانتهاء من التسجيل")
        
        # إغلاق الدفق
        stream.stop_stream()
        stream.close()
        
        return frames, FORMAT, CHANNELS, RATE
    
    except Exception as e:
        print(f"خطأ في اختبار التسجيل: {e}")
        traceback.print_exc()
        
        if stream:
            try:
                stream.close()
            except:
                pass
        
        return None, None, None, None
    finally:
        if p:
            p.terminate()

def test_playback(frames, format_type, channels, rate, output_device=None):
    """اختبار تشغيل الصوت المسجل"""
    if not frames:
        print("لا توجد بيانات صوتية للتشغيل")
        return False
    
    p = None
    stream = None
    
    try:
        print("\n=== اختبار تشغيل الصوت المسجل ===")
        
        p = pyaudio.PyAudio()
        
        # تحديد جهاز الإخراج
        if output_device is not None:
            try:
                device_info = p.get_device_info_by_index(output_device)
                print(f"استخدام جهاز الإخراج: {output_device} - {device_info['name']}")
            except:
                print(f"تحذير: لم يتم العثور على جهاز الإخراج {output_device}. استخدام الجهاز الافتراضي.")
                output_device = None
        
        # إنشاء دفق التشغيل
        stream = p.open(
            format=format_type,
            channels=channels,
            rate=rate,
            output=True,
            output_device_index=output_device
        )
        
        print("تم فتح دفق التشغيل بنجاح")
        print("جاري تشغيل الصوت المسجل...")
        
        # تشغيل البيانات المسجلة
        for frame in frames:
            stream.write(frame)
        
        print("تم الانتهاء من تشغيل الصوت")
        
        # إغلاق الدفق
        stream.stop_stream()
        stream.close()
        
        return True
    
    except Exception as e:
        print(f"خطأ في تشغيل الصوت: {e}")
        traceback.print_exc()
        
        if stream:
            try:
                stream.close()
            except:
                pass
        
        return False
    finally:
        if p:
            p.terminate()

def run_full_test(input_device=None, output_device=None, seconds=3):
    """تشغيل اختبار كامل للتسجيل والتشغيل"""
    try:
        print("\n==================================================")
        print("بدء اختبار الصوت الكامل")
        print("==================================================")
        
        # طباعة معلومات الأجهزة
        print_audio_devices()
        
        # اختبار التسجيل
        frames, format_type, channels, rate = test_recording(seconds, input_device)
        
        if frames:
            # اختبار التشغيل
            success = test_playback(frames, format_type, channels, rate, output_device)
            
            print("\n==================================================")
            if success:
                print("✅ تم اجتياز اختبار الصوت بنجاح!")
                print("إذا سمعت الصوت المسجل، فهذا يعني أن نظام الصوت يعمل بشكل صحيح.")
            else:
                print("❌ فشل اختبار الصوت - تم التسجيل ولكن فشل التشغيل")
        else:
            print("\n==================================================")
            print("❌ فشل اختبار الصوت - لم يتم التسجيل بنجاح")
        
        print("==================================================")
    
    except Exception as e:
        print(f"خطأ غير متوقع في اختبار الصوت: {e}")
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='أداة اختبار الصوت للدردشة الصوتية')
    parser.add_argument('--list', action='store_true', help='عرض قائمة بأجهزة الصوت المتاحة')
    parser.add_argument('--input', type=int, help='تحديد جهاز الإدخال برقم الفهرس')
    parser.add_argument('--output', type=int, help='تحديد جهاز الإخراج برقم الفهرس')
    parser.add_argument('--time', type=int, default=3, help='مدة تسجيل الصوت بالثواني')
    
    args = parser.parse_args()
    
    try:
        if args.list:
            print_audio_devices()
        else:
            run_full_test(args.input, args.output, args.time)
    except KeyboardInterrupt:
        print("\nتم إلغاء الاختبار")
    except Exception as e:
        print(f"خطأ: {e}")
        traceback.print_exc()
    finally:
        print("\nانتهى اختبار الصوت")

if __name__ == "__main__":
    main() 