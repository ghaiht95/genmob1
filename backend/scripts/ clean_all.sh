#!/bin/bash

# إعدادات قاعدة البيانات
DB_NAME="game_room"
DB_USER="postgres"

# إعدادات SoftEther VPN
VPNCMD="/opt/vpnserver/vpncmd"
SERVER_IP="127.0.0.1"
SERVER_PORT="5555"  # عدلها إذا كنت تستخدم بورت مختلف
HUB_PREFIX="room_"

echo "🧹 بدء تنظيف قاعدة البيانات..."

# حذف من جدول اللاعبين
psql -U "$DB_USER" -d "$DB_NAME" -c "DELETE FROM room_player;"

# حذف من جدول المحادثات
psql -U "$DB_USER" -d "$DB_NAME" -c "DELETE FROM chat_message;"

# استخراج جميع معرفات الغرف قبل حذفها
ROOM_IDS=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT id FROM room;")

# حذف الغرف
psql -U "$DB_USER" -d "$DB_NAME" -c "DELETE FROM room;"

echo "✅ تم تنظيف الجداول."

echo "🧹 بدء حذف VPN hubs..."

# حذف كل hub مرتبط برقم غرفة
for id in $ROOM_IDS
do
    HUB_NAME="${HUB_PREFIX}${id}"
    echo "➖ حذف hub: $HUB_NAME"
    "$VPNCMD" "$SERVER_IP:$SERVER_PORT" /SERVER /CMD HubDelete "$HUB_NAME" /PASSWORD:admin
done

echo "✅ تم حذف جميع الـ hubs."
echo "🎉 التنظيف الكامل انتهى."
