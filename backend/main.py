import logging
import uvicorn
from app_setup import socket_app

# تعطيل أو تقليل مستوى السجلات الخاصة بـ engineio و socketio
logging.getLogger('engineio.server').setLevel(logging.WARNING)
logging.getLogger('socketio.server').setLevel(logging.WARNING)
logging.getLogger('socket_events').setLevel(logging.WARNING)

if __name__ == "__main__":
    uvicorn.run(
        socket_app,
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="warning"  # يعرض فقط التحذيرات والأخطاء
    )
