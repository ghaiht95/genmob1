import subprocess
import os

# إعدادات الشبكة والسيرفر
interface_name = "wg0"
address = "10.0.0.1/24"
listen_port = 51820
save_config = True
key_dir = "keys"
config_dir = "/etc/wireguard"
config_path = os.path.join(config_dir, f"{interface_name}.conf")

# إنشاء مجلد لحفظ المفاتيح إذا لم يكن موجود
os.makedirs(key_dir, exist_ok=True)

# توليد المفتاح الخاص
private_key = subprocess.check_output(['wg', 'genkey']).strip()
with open(os.path.join(key_dir, f"{interface_name}_privatekey"), 'wb') as f:
    f.write(private_key)

# توليد المفتاح العام
public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key).strip()
with open(os.path.join(key_dir, f"{interface_name}_publickey"), 'wb') as f:
    f.write(public_key)

# إنشاء محتوى ملف الإعداد للسيرفر
config_content = f"""[Interface]
PrivateKey = {private_key.decode()}
Address = {address}
ListenPort = {listen_port}
SaveConfig = {'true' if save_config else 'false'}
"""

# حفظ ملف الإعداد
os.makedirs(config_dir, exist_ok=True)
with open(config_path, 'w') as f:
    f.write(config_content)

print(f"تم توليد ملف إعداد الخادم '{config_path}' ومفاتيح '{key_dir}'")
print("Public Key (server):", public_key.decode())