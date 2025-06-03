#!/usr/bin/env python3
"""
WireGuard Detection Utility
أداة لاكتشاف موقع WireGuard على النظام
"""

import os
import sys
import subprocess
import glob

def scan_common_locations():
    """Scan common WireGuard installation locations"""
    print("🔍 جاري البحث عن WireGuard في المواقع الشائعة...")
    
    locations = []
    
    # Standard installation paths
    standard_paths = [
        r"C:\Program Files\WireGuard\wireguard.exe",
        r"C:\Program Files (x86)\WireGuard\wireguard.exe",
    ]
    
    # User-specific paths
    user_profile = os.environ.get('USERPROFILE', '')
    if user_profile:
        user_paths = [
            os.path.join(user_profile, 'Desktop', '**', 'wireguard.exe'),
            os.path.join(user_profile, 'Downloads', '**', 'wireguard.exe'),
            os.path.join(user_profile, 'Documents', '**', 'wireguard.exe'),
        ]
        standard_paths.extend(user_paths)
    
    # Common portable locations
    portable_paths = [
        r"C:\Tools\**\wireguard.exe",
        r"C:\PortableApps\**\wireguard.exe",
        r"C:\WireGuard\wireguard.exe",
    ]
    
    all_patterns = standard_paths + portable_paths
    
    for pattern in all_patterns:
        if '**' in pattern:
            # Use glob for recursive search
            try:
                matches = glob.glob(pattern, recursive=True)
                for match in matches:
                    if verify_wireguard(match):
                        locations.append(match)
            except:
                continue
        else:
            # Direct path check
            if os.path.exists(pattern) and verify_wireguard(pattern):
                locations.append(pattern)
    
    return locations

def verify_wireguard(path):
    """Verify if the executable is actually WireGuard"""
    try:
        result = subprocess.run([path, '/help'], capture_output=True, text=True, timeout=5)
        return result.returncode == 0 or "WireGuard" in result.stdout
    except:
        return False

def search_in_registry():
    """Search for WireGuard in Windows registry"""
    print("🔍 جاري البحث في سجل Windows...")
    
    locations = []
    
    try:
        import winreg
        
        # Check common registry locations
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WireGuard"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WireGuard"),
        ]
        
        for hkey, subkey in registry_paths:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    try:
                        install_location = winreg.QueryValueEx(key, "InstallLocation")[0]
                        exe_path = os.path.join(install_location, "wireguard.exe")
                        if os.path.exists(exe_path) and verify_wireguard(exe_path):
                            locations.append(exe_path)
                    except:
                        pass
            except:
                continue
                
    except ImportError:
        print("⚠️ winreg module not available")
    
    return locations

def scan_path_environment():
    """Check PATH environment variable"""
    print("🔍 جاري فحص متغير PATH...")
    
    try:
        result = subprocess.run(['where', 'wireguard.exe'], capture_output=True, text=True)
        if result.returncode == 0:
            paths = [p.strip() for p in result.stdout.split('\n') if p.strip()]
            return [p for p in paths if verify_wireguard(p)]
    except:
        pass
    
    return []

def create_config_file(selected_path):
    """Create wireguard_config.txt with the selected path"""
    config_file = "wireguard_config.txt"
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(f"# WireGuard Path Configuration\n")
            f.write(f"# تم إنشاء هذا الملف تلقائياً\n")
            f.write(f"# Created automatically on {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(selected_path)
        
        print(f"✅ تم إنشاء ملف الإعداد: {config_file}")
        print(f"✅ المسار المحفوظ: {selected_path}")
        return True
    except Exception as e:
        print(f"❌ فشل في إنشاء ملف الإعداد: {e}")
        return False

def main():
    print("🚀 أداة اكتشاف WireGuard")
    print("=" * 50)
    
    all_locations = []
    
    # Scan common locations
    common_locations = scan_common_locations()
    all_locations.extend(common_locations)
    
    # Search registry
    registry_locations = search_in_registry()
    all_locations.extend(registry_locations)
    
    # Check PATH
    path_locations = scan_path_environment()
    all_locations.extend(path_locations)
    
    # Remove duplicates
    unique_locations = list(set(all_locations))
    
    print("\n" + "=" * 50)
    
    if not unique_locations:
        print("❌ لم يتم العثور على WireGuard")
        print("\nيرجى:")
        print("1. تثبيت WireGuard من: https://www.wireguard.com/install/")
        print("2. أو تحديد موقع ملف wireguard.exe يدوياً")
        return
    
    print(f"✅ تم العثور على {len(unique_locations)} موقع لـ WireGuard:")
    print()
    
    for i, location in enumerate(unique_locations, 1):
        print(f"{i}. {location}")
    
    print()
    
    if len(unique_locations) == 1:
        selected_path = unique_locations[0]
        print(f"🎯 سيتم استخدام: {selected_path}")
    else:
        try:
            choice = input(f"اختر رقم (1-{len(unique_locations)}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(unique_locations):
                selected_path = unique_locations[choice_num - 1]
                print(f"🎯 تم اختيار: {selected_path}")
            else:
                print("❌ اختيار غير صحيح")
                return
        except (ValueError, KeyboardInterrupt):
            print("\n❌ تم الإلغاء")
            return
    
    # Create config file
    if create_config_file(selected_path):
        print("\n🎉 تم الإعداد بنجاح!")
        print("يمكنك الآن تشغيل التطبيق مرة أخرى.")
    
if __name__ == "__main__":
    import time
    main()
    input("\nاضغط Enter للخروج...") 