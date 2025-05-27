import subprocess
import os

# إعدادات الاتصال بالسيرفر
server_public_key = "PJwX/7cGmrZ2sIIMh+Iq7P6l0MbDINvtTd9m9J7ENn0="
server_endpoint = "31.220.80.192:51820"  # استبدلها بعنوان الـ DNS أو IP للسيرفر والمنفذ
client_address = "10.0.0.3/32"  # عنوان IP للعميل
allowed_ips = "0.0.0.0/0, ::/0"  # الشبكات المسموح بها عبر النفق

# مسارات الملفات
client_name = "client2"
key_dir = "keys"
config_dir = "clients"
os.makedirs(key_dir, exist_ok=True)
os.makedirs(config_dir, exist_ok=True)

# توليد المفتاح الخاص للعميل
private_key = subprocess.check_output(['wg', 'genkey']).strip()
with open(os.path.join(key_dir, f"{client_name}_privatekey"), 'wb') as f:
    f.write(private_key)

# توليد المفتاح العام للعميل
public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key).strip()
with open(os.path.join(key_dir, f"{client_name}_publickey"), 'wb') as f:
    f.write(public_key)

# توليد مفتاح preshared اختياري (يمكن تجاهله)
# psk = subprocess.check_output(['wg', 'genpsk']).strip()

# توليد ملف الإعداد للعميل
config_content = f"""[Interface]
PrivateKey = {private_key.decode()}
Address = {client_address}
DNS = 1.1.1.1

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_endpoint}
AllowedIPs = {allowed_ips}
PersistentKeepalive = 25
# PresharedKey = {psk.decode() if 'psk' in locals() else ''}
"""

config_path = os.path.join(config_dir, f"{client_name}.conf")
with open(config_path, 'w') as f:
    f.write(config_content)

print(f"تم توليد ملف إعداد العميل '{config_path}' ومفاتيح '{key_dir}'")
print("Public Key (client):", public_key.decode())