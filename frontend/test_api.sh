#!/bin/bash

# Script para ejecutar el test de conexión a la API

# Verificar que socketio esté instalado
if ! python3 -c "import socketio" &> /dev/null; then
    echo "📦 تثبيت مكتبة socketio..."
    pip install python-socketio
fi

# Verificar que requests esté instalado
if ! python3 -c "import requests" &> /dev/null; then
    echo "📦 تثبيت مكتبة requests..."
    pip install requests
fi

# Ejecutar el script de prueba
echo "🚀 تشغيل اختبار الاتصال بواجهة برمجة التطبيقات..."
python3 test_api_connection.py

# Final
echo ""
echo "تم الانتهاء من الاختبار!" 