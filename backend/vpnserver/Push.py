import subprocess

# إعدادات العميل
client_public_key = "rraYnXpqjeERMn6UQnYm9cC4qSzpEjUWNuSViuIxlzw="
client_allowed_ips = "10.0.0.3/32"
client_preshared_key = ""

# اسم الواجهة
interface_name = "wg0"

# أوامر الدفع
try:
    # إضافة العميل بدون preshared key
    if client_preshared_key == "":
        subprocess.run([
            'sudo', 'wg', 'set', interface_name,
            'peer', client_public_key,
            'allowed-ips', client_allowed_ips
        ], check=True)
    else:
        subprocess.run([
            'sudo', 'wg', 'set', interface_name,
            'peer', client_public_key,
            'preshared-key', f'/tmp/{interface_name}_psk',
            'allowed-ips', client_allowed_ips
        ], check=True)

    print(f"تم دفع العميل {client_public_key} إلى السيرفر {interface_name}")
except subprocess.CalledProcessError:
    print("حدث خطأ أثناء دفع العميل إلى السيرفر")