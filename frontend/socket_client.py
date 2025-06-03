import socketio

class SocketManager:
    def __init__(self):
        self.socket = socketio.Client()
        self.connected = False

    def connect(self, server_url):
        if not self.connected:
            self.socket.connect(server_url, namespaces=["/game"])
            self.connected = True

    def disconnect(self):
        try:
            if self.connected:
                self.socket.disconnect()
                self.connected = False
        except Exception as e:
            print(f"Error in socket disconnect: {e}")
            self.connected = False

    def on(self, event, handler, namespace="/game"):
        self.socket.on(event, handler, namespace=namespace)

    def emit(self, event, data, namespace="/game"):
        self.socket.emit(event, data, namespace=namespace)

socket_manager = SocketManager()  