import subprocess

# اسم الواجهة (مثلاً wg0)
interface_name = "wg0"

try:
    # أمر لتشغيل الواجهة باستخدام wg-quick
    subprocess.run(['sudo', 'wg-quick', 'up', interface_name], check=True)
    print(f"تم تشغيل واجهة WireGuard: {interface_name}")
except subprocess.CalledProcessError:
    print(f"حدث خطأ أثناء تشغيل واجهة WireGuard: {interface_name}")