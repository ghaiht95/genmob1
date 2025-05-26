#!/bin/bash

# إنشاء مجلد لحفظ التصدير
EXPORT_DIR="db_exports"
mkdir -p "$EXPORT_DIR"

# قائمة الجداول المراد تصديرها
tables=("user" "room" "room_player" "chat_message" "friendship" "alembic_version")

# تصدير كل جدول إلى ملف CSV
for table in "${tables[@]}"
do
  echo "📤 Exporting table: $table"
  sudo -u postgres psql -d game_room -c "\COPY \"$table\" TO '$EXPORT_DIR/${table}.csv' CSV HEADER"
done

echo "✅ All tables exported to $EXPORT_DIR/"
