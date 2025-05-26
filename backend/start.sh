#!/bin/bash
cd /opt/app2/backend
source /opt/app2/venv/bin/activate
exec uvicorn main:socket_app --host 0.0.0.0 --port 5000 --reload