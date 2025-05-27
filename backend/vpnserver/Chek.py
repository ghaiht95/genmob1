import subprocess

# إعدادات العميل
client_public_key = "2CeZM3zsjLRY3aoneEHTP/XLe3M048KIONuYX0US9H0="
interface_name = "wg0"  # اسم الواجهة

try:
    # أمر حذف العميل من السيرفر
    subprocess.run([
        'sudo', 'wg', 'set', interface_name,
        'peer', client_public_key,
        'remove'
    ], check=True)
    print(f"تم حذف العميل {client_public_key} من السيرفر {interface_name}")
except subprocess.CalledProcessError:
    print("حدث خطأ أثناء حذف العميل من السيرفر")