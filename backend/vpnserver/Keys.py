import subprocess
import os

# إنشاء مجلد لحفظ المفاتيح إذا لم يكن موجوداً
key_dir = "keys"
os.makedirs(key_dir, exist_ok=True)

# توليد المفتاح الخاص
private_key = subprocess.check_output(['wg', 'genkey']).strip()
# توليد المفتاح العام بناءً على المفتاح الخاص
public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key).strip()

# حفظ المفاتيح في ملفات
with open(os.path.join(key_dir, 'privatekey'), 'wb') as f:
    f.write(private_key)

with open(os.path.join(key_dir, 'publickey'), 'wb') as f:
    f.write(public_key)

print(f"تم توليد وحفظ المفاتيح في المجلد '{key_dir}'")
print("Private Key:", private_key.decode())
print("Public Key: ", public_key.decode())