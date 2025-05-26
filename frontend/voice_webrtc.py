import logging
import os
import threading
import time
from typing import Dict, Optional, Callable

import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal

# Intentar importar aiortc, pero no fallar si no está disponible
try:
    import asyncio
    import json
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
    from aiortc.contrib.media import MediaStreamTrack, MediaBlackhole, MediaRecorder
    from aiortc.mediastreams import MediaStreamError, AudioStreamTrack
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    print("⚠️ WebRTC (aiortc) no está disponible. Se usará el modo de compatibilidad.")

logger = logging.getLogger(__name__)

# Configuración de STUN/TURN servers para facilitar conexiones NAT
ICE_SERVERS = [
    {"urls": ["stun:stun.l.google.com:19302"]},
    {"urls": ["stun:stun1.l.google.com:19302"]},
]

# Clases WebRTC solo están disponibles si aiortc está instalado
if WEBRTC_AVAILABLE:
    class AudioReceiveTrack(MediaStreamTrack):
        """
        Una pista para recibir audio de otros participantes
        """
        kind = "audio"
        
        def __init__(self, track, participant_id):
            super().__init__()
            self.track = track
            self.participant_id = participant_id
            
        async def recv(self):
            frame = await self.track.recv()
            return frame

    class MicrophoneStreamTrack(AudioStreamTrack):
        """
        Una pista que captura audio del micrófono
        """
        kind = "audio"
        
        def __init__(self):
            super().__init__()
            self._queue = asyncio.Queue()
            self._start = time.time()
            self._sample_rate = 48000
            self._samples_per_frame = 960  # 20ms at 48kHz
            self._active = True
            self._ended_handlers = []
            
        async def recv(self):
            """
            Entrega frames de audio para WebRTC
            """
            if not self._active:
                # Si la pista fue marcada como inactiva, disparar evento 'ended'
                self._dispatch_ended()
                frame = self._create_silence_frame()
                frame.pts = None  # Indica que la pista ha terminado
                return frame
                
            if self._queue.empty():
                # Si no hay datos, generamos silencio
                silence_frame = self._create_silence_frame()
                return silence_frame
            else:
                # Obtener datos de audio de la cola
                try:
                    frame = await self._queue.get()
                    return frame
                except Exception as e:
                    logger.error(f"Error al recibir audio: {e}")
                    return self._create_silence_frame()
        
        def _create_silence_frame(self):
            """
            Crea un frame de silencio si no hay datos disponibles
            """
            from aiortc.mediastreams import AudioFrame
            from av import AudioFrame as AVAudioFrame
            import av
            
            # Crear un frame de silencio
            samples = np.zeros(self._samples_per_frame, dtype=np.int16)
            avframe = AVAudioFrame.from_ndarray(
                samples,
                format="s16",
                layout="mono"
            )
            avframe.sample_rate = self._sample_rate
            avframe.time_base = av.Rational(1, self._sample_rate)
            
            # Establecer PTS (Presentation TimeStamp)
            elapsed_time = time.time() - self._start
            avframe.pts = int(elapsed_time * self._sample_rate)
            
            return AudioFrame(avframe)
        
        def add_audio(self, audio_data):
            """
            Añade datos de audio a la cola para ser enviados
            audio_data: numpy array de audio con valores int16
            """
            if not self._active:
                return
                
            try:
                from aiortc.mediastreams import AudioFrame
                from av import AudioFrame as AVAudioFrame
                import av
                
                # Convertir a frame de audio
                avframe = AVAudioFrame.from_ndarray(
                    audio_data,
                    format="s16",
                    layout="mono"
                )
                avframe.sample_rate = self._sample_rate
                avframe.time_base = av.Rational(1, self._sample_rate)
                
                # Establecer PTS (Presentation TimeStamp)
                elapsed_time = time.time() - self._start
                avframe.pts = int(elapsed_time * self._sample_rate)
                
                # Crear AudioFrame y añadirlo a la cola
                frame = AudioFrame(avframe)
                asyncio.run_coroutine_threadsafe(self._queue.put(frame), asyncio.get_event_loop())
                
            except Exception as e:
                logger.error(f"Error al añadir audio: {e}")
                import traceback
                traceback.print_exc()
        
        def stop(self):
            """
            Detiene la pista y libera recursos
            """
            logger.info("Deteniendo MicrophoneStreamTrack")
            self._active = False
            # Limpiar la cola para no almacenar más datos
            asyncio.run_coroutine_threadsafe(self._clear_queue(), asyncio.get_event_loop())
        
        async def _clear_queue(self):
            """Vacía la cola de audio pendiente"""
            try:
                while not self._queue.empty():
                    await self._queue.get()
            except Exception as e:
                logger.error(f"Error limpiando cola de audio: {e}")
        
        def on_ended(self, callback):
            """Añade un manejador para el evento 'ended'"""
            self._ended_handlers.append(callback)
            
        def _dispatch_ended(self):
            """Dispara el evento 'ended' a todos los manejadores registrados"""
            for handler in self._ended_handlers:
                try:
                    asyncio.run_coroutine_threadsafe(handler(), asyncio.get_event_loop())
                except Exception as e:
                    logger.error(f"Error en manejador de evento 'ended': {e}")

    class WebRTCVoiceChat(QtCore.QObject):
        """
        Implementación de chat de voz usando WebRTC
        """
        # Señales
        audio_received = pyqtSignal(bytes, str)  # datos de audio, ID del participante
        participant_connected = pyqtSignal(str)
        participant_disconnected = pyqtSignal(str)
        connection_state_changed = pyqtSignal(str, str)  # participante, estado
        
        def __init__(self, signaling_url, room_id, local_id):
            super().__init__()
            self.signaling_url = signaling_url
            self.room_id = room_id
            self.local_id = local_id
            
            # Estado
            self.is_connected = False
            self.is_muted = True
            
            # Pista de audio del micrófono
            self.mic_track = MicrophoneStreamTrack()
            
            # Conexiones peer
            self.peer_connections: Dict[str, RTCPeerConnection] = {}
            
            # Socket.IO instance for signaling
            self.socket = None  # Will be set in _connect_signaling
            
            # Bucle asíncrono y thread
            self._loop = asyncio.new_event_loop()
            self._thread = None
            
            # Audioo callbacks
            self._on_audio_callback = None
            
            # Lista de pistas activas
            self._active_tracks = {}
        
        def set_on_audio_callback(self, callback: Callable[[bytes, str], None]):
            """
            Establece el callback para cuando se recibe audio
            """
            self._on_audio_callback = callback
        
        def start(self):
            """
            Inicia el chat de voz
            """
            if self._thread is not None:
                return
                
            # Crear y arrancar el thread para el bucle async
            self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self._thread.start()
            
            logger.info("WebRTC voice chat iniciado")
        
        def _run_async_loop(self):
            """
            Ejecuta el bucle async en un thread separado
            """
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run_webrtc())
        
        async def _run_webrtc(self):
            """
            Bucle principal de WebRTC
            """
            # Iniciar la conexión de señalización
            await self._connect_signaling()
            
            # Notificar a otros usuarios que este usuario se ha unido
            if self.socket:
                self.socket.emit('webrtc_join', {
                    'room_id': self.room_id,
                    'username': self.local_id
                })
            
            # Bucle principal
            while True:
                try:
                    # Esperar un poco para no saturar el sistema
                    await asyncio.sleep(0.01)
                    
                except Exception as e:
                    logger.error(f"Error en el bucle WebRTC: {e}")
                    await asyncio.sleep(1)
        
        async def _connect_signaling(self):
            """
            Conecta con el servidor de señalización
            """
            try:
                import socketio
                
                # Crear cliente Socket.IO
                sio = socketio.Client()
                
                @sio.on('connect')
                def on_connect():
                    logger.info("WebRTC: Connected to signaling server")
                    self.is_connected = True
                
                @sio.on('disconnect')
                def on_disconnect():
                    logger.info("WebRTC: Disconnected from signaling server")
                    self.is_connected = False
                
                @sio.on('webrtc_offer')
                def on_offer(data):
                    asyncio.run_coroutine_threadsafe(self._handle_offer(data), self._loop)
                
                @sio.on('webrtc_answer')
                def on_answer(data):
                    asyncio.run_coroutine_threadsafe(self._handle_answer(data), self._loop)
                
                @sio.on('webrtc_ice_candidate')
                def on_ice_candidate(data):
                    asyncio.run_coroutine_threadsafe(self._handle_ice_candidate(data), self._loop)
                
                @sio.on('webrtc_peers')
                def on_peers(data):
                    peers = data.get('peers', [])
                    logger.info(f"WebRTC: Room has {len(peers)} other peers: {peers}")
                    for peer_id in peers:
                        asyncio.run_coroutine_threadsafe(self._create_peer_connection_for(peer_id), self._loop)
                
                @sio.on('webrtc_new_peer')
                def on_new_peer(data):
                    new_peer = data.get('username')
                    logger.info(f"WebRTC: New peer joined: {new_peer}")
                    # No need to do anything, they will initiate connection
                
                @sio.on('webrtc_error')
                def on_error(data):
                    error = data.get('error')
                    message = data.get('message')
                    logger.error(f"WebRTC signaling error: {error} - {message}")
                
                # Intentamos conectar al servidor
                sio.connect(self.signaling_url)
                self.socket = sio
                
                logger.info(f"Conectado al servidor de señalización: {self.signaling_url}")
                
            except Exception as e:
                logger.error(f"Error al conectar al servidor de señalización: {e}")
                import traceback
                traceback.print_exc()
                self.is_connected = False
        
        async def _send_signaling_message(self, message):
            """
            Envía un mensaje al servidor de señalización
            """
            if not self.socket:
                logger.error("No se puede enviar mensaje - no hay conexión al servidor de señalización")
                return
            
            try:
                message_type = message.get('type')
                
                if message_type == 'offer':
                    self.socket.emit('webrtc_offer', {
                        'room_id': self.room_id,
                        'from': self.local_id,
                        'to': message.get('to'),
                        'sdp': message.get('sdp')
                    })
                    
                elif message_type == 'answer':
                    self.socket.emit('webrtc_answer', {
                        'room_id': self.room_id,
                        'from': self.local_id,
                        'to': message.get('to'),
                        'sdp': message.get('sdp')
                    })
                    
                elif message_type == 'candidate':
                    self.socket.emit('webrtc_ice_candidate', {
                        'room_id': self.room_id,
                        'from': self.local_id,
                        'to': message.get('to'),
                        'candidate': message.get('candidate'),
                        'sdpMid': message.get('sdpMid'),
                        'sdpMLineIndex': message.get('sdpMLineIndex')
                    })
                    
                elif message_type == 'join':
                    self.socket.emit('webrtc_join', {
                        'room_id': self.room_id,
                        'username': self.local_id
                    })
                    
                else:
                    logger.warning(f"Tipo de mensaje desconocido: {message_type}")
                
            except Exception as e:
                logger.error(f"Error al enviar mensaje de señalización: {e}")
                import traceback
                traceback.print_exc()
        
        async def _create_peer_connection_for(self, peer_id):
            """
            Crea y configura una conexión con un peer específico e inicia la oferta
            """
            logger.info(f"Creating peer connection for {peer_id}")
            pc = self._get_or_create_peer_connection(peer_id)
            
            # Crear oferta si no estamos silenciados
            if not self.is_muted:
                offer = await pc.createOffer()
                await pc.setLocalDescription(offer)
                
                # Enviar la oferta
                await self._send_signaling_message({
                    "type": "offer",
                    "to": peer_id,
                    "from": self.local_id,
                    "sdp": pc.localDescription.sdp
                })
            
            return pc
        
        async def _handle_offer(self, data):
            """
            Maneja una oferta WebRTC recibida del servidor
            """
            peer_id = data.get('from')
            sdp = data.get('sdp')
            
            if not peer_id or not sdp:
                logger.error("Oferta WebRTC inválida")
                return
            
            logger.info(f"Recibida oferta de {peer_id}")
            
            # Crear o obtener la conexión peer
            pc = self._get_or_create_peer_connection(peer_id)
            
            # Establecer la descripción remota
            offer = RTCSessionDescription(sdp=sdp, type="offer")
            await pc.setRemoteDescription(offer)
            
            # Crear respuesta
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            # Enviar la respuesta
            await self._send_signaling_message({
                "type": "answer",
                "to": peer_id,
                "from": self.local_id,
                "sdp": pc.localDescription.sdp
            })
            
            # Notificar que se ha establecido conexión
            self.participant_connected.emit(peer_id)
        
        async def _handle_answer(self, data):
            """
            Maneja una respuesta WebRTC recibida del servidor
            """
            peer_id = data.get('from')
            sdp = data.get('sdp')
            
            if not peer_id or not sdp:
                logger.error("Respuesta WebRTC inválida")
                return
            
            logger.info(f"Recibida respuesta de {peer_id}")
            
            # Obtener la conexión peer
            pc = self.peer_connections.get(peer_id)
            if not pc:
                logger.error(f"No se encontró conexión peer para {peer_id}")
                return
            
            # Establecer la descripción remota
            answer = RTCSessionDescription(sdp=sdp, type="answer")
            await pc.setRemoteDescription(answer)
            
            # Notificar que se ha establecido conexión
            self.participant_connected.emit(peer_id)
        
        async def _handle_ice_candidate(self, data):
            """
            Maneja un candidato ICE recibido del servidor
            """
            peer_id = data.get('from')
            candidate = data.get('candidate')
            sdpMid = data.get('sdpMid')
            sdpMLineIndex = data.get('sdpMLineIndex')
            
            if not peer_id or not candidate:
                logger.error("Candidato ICE inválido")
                return
            
            # Obtener la conexión peer
            pc = self.peer_connections.get(peer_id)
            if not pc:
                logger.error(f"No se encontró conexión peer para {peer_id}")
                return
            
            # Añadir el candidato ICE
            try:
                candidate_obj = RTCIceCandidate(
                    component=candidate.get('component', 1),
                    foundation=candidate.get('foundation', ''),
                    ip=candidate.get('ip', ''),
                    port=candidate.get('port', 0),
                    priority=candidate.get('priority', 0),
                    protocol=candidate.get('protocol', ''),
                    type=candidate.get('type', ''),
                    sdpMid=sdpMid,
                    sdpMLineIndex=sdpMLineIndex
                )
                await pc.addIceCandidate(candidate_obj)
                logger.debug(f"Candidato ICE añadido para {peer_id}")
            except Exception as e:
                logger.error(f"Error al añadir candidato ICE: {e}")
                import traceback
                traceback.print_exc()
        
        def _get_or_create_peer_connection(self, peer_id):
            """
            Obtiene o crea una conexión peer
            """
            if peer_id in self.peer_connections:
                return self.peer_connections[peer_id]
            
            # Crear nueva conexión
            pc = RTCPeerConnection(configuration={"iceServers": ICE_SERVERS})
            
            # Manejar cambios de estado de conexión
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                state = pc.connectionState
                logger.info(f"Conexión {peer_id} cambió a estado: {state}")
                self.connection_state_changed.emit(peer_id, state)
                
                if state == "failed" or state == "closed":
                    if peer_id in self.peer_connections:
                        del self.peer_connections[peer_id]
            
            # Manejar candidatos ICE
            @pc.on("icecandidate")
            async def on_icecandidate(candidate):
                if candidate:
                    await self._send_signaling_message({
                        "type": "candidate",
                        "to": peer_id,
                        "from": self.local_id,
                        "candidate": {
                            "component": candidate.component,
                            "foundation": candidate.foundation,
                            "ip": candidate.ip,
                            "port": candidate.port,
                            "priority": candidate.priority,
                            "protocol": candidate.protocol,
                            "type": candidate.type
                        },
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex
                    })
            
            # Manejar pistas entrantes
            @pc.on("track")
            async def on_track(track):
                logger.info(f"Pista recibida de {peer_id}: {track.kind}")
                
                if track.kind == "audio":
                    # Crear una pista de recepción
                    audio_track = AudioReceiveTrack(track, peer_id)
                    
                    # Registrar la pista para seguimiento
                    track_id = f"audio_{time.time()}_{id(track)}"
                    if peer_id not in self._active_tracks:
                        self._active_tracks[peer_id] = {}
                    self._active_tracks[peer_id][track_id] = audio_track
                    
                    # Notificar que se ha recibido una pista de audio
                    self.connection_state_changed.emit(peer_id, "audioStarted")
                    
                    # Manejar evento 'ended'
                    @track.on("ended")
                    async def on_ended():
                        logger.info(f"Pista de audio de {peer_id} terminada")
                        # Limpiar recursos cuando la pista termine
                        try:
                            # Buscar y eliminar esta pista de los tracks activos
                            for sender in pc.getSenders():
                                if sender.track == track:
                                    pc.removeTrack(sender)
                                    logger.info(f"Pista eliminada de PC para {peer_id}")
                            
                            # Eliminar del registro de pistas activas
                            if peer_id in self._active_tracks and track_id in self._active_tracks[peer_id]:
                                del self._active_tracks[peer_id][track_id]
                                if not self._active_tracks[peer_id]:
                                    del self._active_tracks[peer_id]
                                    
                            # Notificar desconexión de audio si es apropiado
                            if peer_id in self.peer_connections:
                                self.connection_state_changed.emit(peer_id, "audioEnded")
                                
                            logger.info(f"Recursos de pista de audio limpiados para {peer_id}")
                        except Exception as e:
                            logger.error(f"Error limpiando pista terminada: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    # Manejar procesamiento de marcos de audio
                    async def process_audio_frames():
                        try:
                            while True:
                                try:
                                    # Recibir frame de audio
                                    frame = await audio_track.recv()
                                    
                                    # Verificar si la pista ha terminado
                                    if frame.pts is None:
                                        logger.info(f"Fin de pista detectado para {peer_id}")
                                        break
                                        
                                    # Convertir a bytes para enviar a través de la señal
                                    # Esto depende de cómo procesamos el audio en nuestra aplicación
                                    audio_array = frame.to_ndarray()
                                    audio_bytes = audio_array.tobytes()
                                    
                                    # Enviar a través de la señal (desde el hilo principal)
                                    if self._on_audio_callback:
                                        # Usar QtCore.QMetaObject.invokeMethod si es necesario para seguridad entre hilos
                                        self._on_audio_callback(audio_bytes, peer_id)
                                    
                                    # Emitir la señal
                                    self.audio_received.emit(audio_bytes, peer_id)
                                    
                                except MediaStreamError as e:
                                    logger.error(f"Error en flujo de medios desde {peer_id}: {e}")
                                    break
                                except Exception as e:
                                    logger.error(f"Error procesando audio de {peer_id}: {e}")
                                    
                                # Esperar un poco para no saturar el sistema
                                await asyncio.sleep(0.01)
                                
                        except Exception as e:
                            logger.error(f"Error en bucle de procesamiento de audio: {e}")
                        finally:
                            # Limpiar cuando terminemos
                            if peer_id in self._active_tracks and track_id in self._active_tracks[peer_id]:
                                logger.info(f"Limpiando pista {track_id} para {peer_id} (procesamiento terminado)")
                                del self._active_tracks[peer_id][track_id]
                    
                    # Iniciar el procesamiento de audio en segundo plano
                    asyncio.create_task(process_audio_frames())
            
            # Guardar la conexión
            self.peer_connections[peer_id] = pc
            
            # Añadir la pista de audio si no estamos muteados
            if not self.is_muted:
                pc.addTrack(self.mic_track)
                logger.info(f"Pista de micrófono añadida para {peer_id} durante la creación")
            
            return pc
        
        def add_audio_data(self, audio_data):
            """
            Añade datos de audio para enviar (desde PyAudio)
            audio_data: bytes de audio
            """
            if self.is_muted or not self.is_connected:
                return
                
            try:
                # Convertir bytes a numpy array
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
                
                # Añadir a la pista de audio
                self.mic_track.add_audio(audio_np)
            except Exception as e:
                logger.error(f"Error al añadir datos de audio: {e}")
        
        def toggle_mute(self):
            """
            Alterna el estado de silenciado
            """
            self.is_muted = not self.is_muted
            
            # Actualizar todas las conexiones peer
            async def update_tracks():
                for peer_id, pc in self.peer_connections.items():
                    # En lugar de eliminar y añadir pistas, cambiamos la dirección del transceiver
                    for transceiver in pc.getTransceivers():
                        if transceiver.kind == "audio":
                            transceiver.direction = "inactive" if self.is_muted else "sendrecv"
                            logger.info(f"Transceiver de audio para {peer_id} cambiado a: {transceiver.direction}")
            
            # Ejecutar de forma asíncrona
            asyncio.run_coroutine_threadsafe(update_tracks(), self._loop)
            
            return self.is_muted
        
        def stop(self):
            """
            Detiene el chat de voz
            """
            if not self._thread:
                return
                
            logger.info("Deteniendo WebRTC voice chat")
            
            # Stop the event loop and clean up connections
            try:
                # Use run_coroutine_threadsafe to properly close connections
                future = asyncio.run_coroutine_threadsafe(self._clean_up(), self._loop)
                # Wait for cleanup to complete (with timeout)
                future.result(timeout=5)
                
                # Cancel any remaining tasks
                for task in asyncio.all_tasks(self._loop):
                    task.cancel()
                    
                # Stop the loop
                self._loop.call_soon_threadsafe(self._loop.stop)
                
                # Wait for the thread to finish
                if self._thread and self._thread.is_alive():
                    self._thread.join(timeout=2)
                    
                # Reset variables
                self._thread = None
                
                logger.info("WebRTC voice chat detenido")
            except Exception as e:
                logger.error(f"Error al detener WebRTC voice chat: {e}")
                import traceback
                traceback.print_exc()
            
            self.is_connected = False
        
        async def _clean_up(self):
            """Helper method to clean up connections properly"""
            # Close all peer connections
            await self._close_all_peer_connections()
            
            # Stop microphone track
            if hasattr(self, 'mic_track'):
                self.mic_track.stop()
                
            # Clear active tracks
            self._active_tracks.clear()
            
        async def _close_all_peer_connections(self):
            """Close all peer connections cleanly"""
            close_tasks = []
            for peer_id, pc in list(self.peer_connections.items()):
                logger.info(f"Cerrando conexión con {peer_id}")
                close_tasks.append(pc.close())
                
            # Wait for all connections to close (with timeout)
            if close_tasks:
                done, pending = await asyncio.wait(
                    close_tasks, 
                    timeout=3.0,
                    return_when=asyncio.ALL_COMPLETED
                )
                
                # Cancel any pending tasks
                for task in pending:
                    task.cancel()
                
            # Clear the peer connections dictionary
            self.peer_connections.clear()

# Implementación simplificada que funciona sin WebRTC
class FallbackVoiceChat(QtCore.QObject):
    """Implementación simplificada de chat de voz para cuando WebRTC no está disponible"""
    
    # Señales
    audio_received = pyqtSignal(bytes, str)  # datos de audio, ID del participante
    participant_connected = pyqtSignal(str)
    participant_disconnected = pyqtSignal(str)
    connection_state_changed = pyqtSignal(str, str)  # participante, estado
    
    def __init__(self, socket, room_id, username):
        super().__init__()
        self.socket = socket
        self.room_id = room_id
        self.username = username
        
        # Estado
        self.is_connected = False
        self.is_muted = True
        self._on_audio_callback = None
        
        # Inicializar PyAudio
        try:
            import pyaudio
            self.p = pyaudio.PyAudio()
            self.CHUNK = 512 
            self.FORMAT = pyaudio.paInt16
            self.CHANNELS = 1
            self.RATE = 22050
            
            # Streams de audio
            self.stream_out = None
            self._init_output_stream()
            print("✅ PyAudio inicializado correctamente para Fallback")
        except Exception as e:
            logger.error(f"Error al inicializar PyAudio: {e}")
            self.p = None
            print(f"❌ Error en inicialización de PyAudio: {e}")
        
        # Configurar el manejador de eventos de Socket.IO
        self.socket.on('voice_data', self._on_voice_data_received)
        self.socket.on('voice_error', self._on_voice_error)
        self.socket.on('voice_status', self._on_voice_status)
        
        logger.info("FallbackVoiceChat initialized")
    
    def _init_output_stream(self):
        """Inicializa el stream de salida para reproducción de audio"""
        if not self.p:
            logger.error("No hay PyAudio disponible para inicializar stream de salida")
            return
            
        try:
            # Cerrar stream existente si está abierto
            if self.stream_out and self.stream_out.is_active():
                self.stream_out.stop_stream()
                self.stream_out.close()
                
            self.stream_out = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            print("✅ Stream de salida inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar stream de salida: {e}")
            self.stream_out = None
            print(f"❌ Error al inicializar stream de salida: {e}")
            
    def _on_voice_error(self, data):
        """Manejar errores de voz enviados desde el servidor"""
        error_type = data.get('error', 'unknown')
        message = data.get('message', 'Error desconocido')
        
        logger.error(f"Error de voz recibido: {error_type} - {message}")
        print(f"❌ Error de voz: {message}")
        
        # Intentar reconectar si es necesario
        if error_type in ['room_not_found', 'user_not_in_room']:
            print("🔄 Intentando reconectar a la sala...")
            if self.socket.connected:
                self.socket.emit('join', {
                    'room_id': self.room_id,
                    'username': self.username
                })
    
    def _on_voice_status(self, data):
        """Manejar mensajes de estado de voz enviados desde el servidor"""
        status = data.get('status', '')
        message = data.get('message', '')
        
        logger.info(f"Estado de voz recibido: {status} - {message}")
        print(f"ℹ️ Estado de voz: {message}")
    
    def set_on_audio_callback(self, callback):
        self._on_audio_callback = callback
        
    def _on_voice_data_received(self, data):
        """Manejar los datos de voz recibidos"""
        try:
            username = data.get('username', 'Unknown')
            audio_data = data.get('data')
            
            logger.info(f"Audio recibido de {username} ({len(audio_data) if audio_data else 'No'} bytes)")
            
            # Reproducir audio recibido
            if audio_data and self.stream_out:
                try:
                    if not self.stream_out.is_active():
                        print("⚠️ Stream de salida inactivo, reinicializando...")
                        self._init_output_stream()
                    
                    if self.stream_out and self.stream_out.is_active():
                        self.stream_out.write(audio_data)
                        print(f"✅ Reproducidos {len(audio_data)} bytes de audio de {username}")
                    else:
                        print("❌ No se pudo reproducir el audio - stream inactivo o no disponible")
                except Exception as e:
                    print(f"❌ Error al reproducir audio: {e}")
                    # Intentar reinicializar el stream
                    self._init_output_stream()
            
            # Llamar al callback si está configurado
            if self._on_audio_callback:
                self._on_audio_callback(audio_data, username)
                
            # Emitir la señal
            self.audio_received.emit(audio_data, username)
            
        except Exception as e:
            logger.error(f"Error al procesar audio recibido: {e}")
    
    def start(self):
        """Iniciar chat de voz"""
        self.is_connected = True
        
        # Asegurarse de que el stream de salida esté inicializado
        if not self.stream_out and self.p:
            self._init_output_stream()
            
        # Verificar conexión de socket
        if self.socket and not self.socket.connected:
            logger.warning("Socket no conectado al iniciar chat de voz")
            print("⚠️ Socket no conectado al iniciar chat de voz")
            
        logger.info("Fallback voice chat iniciado")
        
    def stop(self):
        """Detener chat de voz"""
        self.is_connected = False
        
        # Cerrar streams de audio
        if hasattr(self, 'stream_out') and self.stream_out:
            try:
                self.stream_out.stop_stream()
                self.stream_out.close()
                self.stream_out = None
            except Exception as e:
                logger.error(f"Error al cerrar stream de salida: {e}")
        
        # Terminar PyAudio
        if hasattr(self, 'p') and self.p:
            try:
                self.p.terminate()
                self.p = None
            except Exception as e:
                logger.error(f"Error al terminar PyAudio: {e}")
                
        logger.info("Fallback voice chat detenido")
    
    def add_audio_data(self, audio_data):
        """Añadir datos de audio para enviar"""
        if self.is_muted or not self.is_connected:
            return
            
        # Verificar la conexión del socket primero
        if not self.socket or not self.socket.connected:
            logger.warning("No se puede enviar audio - Socket no conectado")
            print("⚠️ No se puede enviar audio - Socket no conectado")
            return
            
        try:
            # Enviar directamente a través de Socket.IO
            self.socket.emit('voice_data', {
                'room_id': self.room_id,
                'username': self.username,
                'data': audio_data
            })
        except Exception as e:
            logger.error(f"Error al enviar audio: {e}")
            print(f"❌ Error al enviar audio: {e}")
    
    def toggle_mute(self):
        """Alternar silenciado"""
        self.is_muted = not self.is_muted
        return self.is_muted
        
    def test_audio_output(self):
        """
        Prueba la reproducción de audio generando un tono de prueba
        """
        if not self.p:
            print("❌ No se puede probar el audio - PyAudio no inicializado")
            return False
            
        if not self.stream_out:
            print("⚠️ Stream de salida no disponible, intentando inicializar...")
            self._init_output_stream()
            
        if not self.stream_out:
            print("❌ No se puede probar el audio - Stream de salida no disponible")
            return False
            
        try:
            # Verificar primero si el stream está activo
            if not self.stream_out.is_active():
                print("⚠️ Stream de salida inactivo, reinicializando...")
                self._init_output_stream()
                
            if not self.stream_out or not self.stream_out.is_active():
                print("❌ No se puede reproducir tono - Stream de salida no disponible")
                return False
            
            # Generar un tono simple (440 Hz - A)
            duration = 0.5  # segundos
            frequency = 440.0  # Hz
            
            # Generar muestras de onda sinusoidal
            sample_rate = 22050
            samples = (duration * sample_rate)
            t = np.linspace(0, duration, int(samples), False)
            tone = np.sin(frequency * t * 2 * np.pi)
            
            # Convertir a int16 (el formato que estamos usando)
            audio_data = (tone * 32767).astype(np.int16).tobytes()
            
            # Reproducir el tono
            self.stream_out.write(audio_data)
            print("✅ Tono de prueba reproducido correctamente")
            
            # Si el socket está conectado, también enviar el tono como prueba
            if self.socket and self.socket.connected and not self.is_muted:
                self.socket.emit('voice_data', {
                    'room_id': self.room_id,
                    'username': self.username,
                    'data': audio_data
                })
                print("✅ Tono de prueba enviado al servidor")
                
            return True
                
        except Exception as e:
            print(f"❌ Error al reproducir tono de prueba: {e}")
            import traceback
            traceback.print_exc()
            return False

# Clase para integrar WebRTC con PyAudio
class WebRTCVoiceBridge:
    """
    Puente entre PyAudio y WebRTC para reutilizar el código existente
    """
    def __init__(self, socket, room_id, username):
        self.socket = socket
        self.room_id = room_id
        self.username = username
        
        # Estado
        self.is_muted = True
        self.is_connected = False
        self.is_recording = False
        
        # URL de señalización (usar Socket.IO existente)
        self.signaling_url = "http://31.220.80.192:5000"
        
        # Cliente WebRTC o Fallback según disponibilidad
        if WEBRTC_AVAILABLE:
            self.webrtc = WebRTCVoiceChat(self.signaling_url, room_id, username)
            self.webrtc.set_on_audio_callback(self._on_audio_received)
            
            # Connect additional signals
            if hasattr(self.webrtc, 'audio_received'):
                # The audio_received signal will now propagate up to RoomWindow
                pass
            
            if hasattr(self.webrtc, 'connection_state_changed'):
                self.webrtc.connection_state_changed.connect(self._on_connection_state_changed)
                
            print("✅ Usando implementación WebRTC completa")
        else:
            self.webrtc = FallbackVoiceChat(socket, room_id, username)
            self.webrtc.set_on_audio_callback(self._on_audio_received)
            print("⚠️ Usando implementación de compatibilidad sin WebRTC")
        
        # Configuración de audio similar a la existente
        self.CHUNK = 512
        self.FORMAT = 16  # bits
        self.CHANNELS = 1
        self.RATE = 48000  # WebRTC usa 48kHz por defecto
        
        # Atributos compatibles con la implementación anterior
        self.stream_in = None
        self.stream_out = None
        self.audio = None
        self.input_device = -1
        self.output_device = -1
    
    def _on_audio_received(self, audio_data, participant_id):
        """
        Callback cuando se recibe audio
        """
        print(f"📥 Recibido audio de {participant_id} ({len(audio_data) if audio_data else 'No'} bytes)")
        
        # Emitir el evento de socket.io para mantener compatibilidad
        self.socket.emit('voice_data_received', {
            'username': participant_id,
            'data': audio_data
        })
        
    def _on_connection_state_changed(self, participant_id, state):
        """
        Callback cuando cambia el estado de una conexión
        """
        print(f"🔄 Estado de conexión para {participant_id}: {state}")
        
        # Map WebRTC states to voice chat states for the UI
        if state == "connected":
            self.socket.emit('voice_status', {
                'participant': participant_id,
                'status': 'connected'
            })
        elif state == "disconnected" or state == "failed":
            self.socket.emit('voice_status', {
                'participant': participant_id,
                'status': 'disconnected'
            })
        elif state == "audioStarted":
            self.socket.emit('voice_status', {
                'participant': participant_id,
                'status': 'audio_started'
            })
        elif state == "audioEnded":
            self.socket.emit('voice_status', {
                'participant': participant_id,
                'status': 'audio_ended'
            })
    
    def start_voice(self):
        """Iniciar chat de voz"""
        if self.is_connected:
            return
            
        self.is_connected = True
        self.webrtc.start()
        
        # Iniciar grabación si no está silenciado
        if not self.is_muted:
            self.start_recording()
            
        print("Voice chat initialized (WebRTC or Fallback)")
    
    def stop_voice(self):
        """Detener chat de voz"""
        if not self.is_connected:
            return
            
        self.stop_recording()
        self.webrtc.stop()
        self.is_connected = False
        
        print("Voice chat stopped")
    
    def toggle_mute(self):
        """Alternar silenciado"""
        self.is_muted = self.webrtc.toggle_mute()
        
        if self.is_connected:
            if self.is_muted:
                self.stop_recording()
            else:
                self.start_recording()
                
        return self.is_muted
    
    def start_recording(self):
        """Compatibilidad con la implementación anterior"""
        self.is_recording = True
        print("Started voice recording")
    
    def stop_recording(self):
        """Compatibilidad con la implementación anterior"""
        self.is_recording = False
        print("Stopped voice recording")
    
    def _init_streams(self):
        """Simulación de inicialización de streams para compatibilidad"""
        print("WebRTC/Fallback no requiere inicialización de streams PyAudio")
        
    def _play_audio(self, audio_data):
        """
        Compatibilidad con la implementación anterior.
        En WebRTC, la reproducción se maneja automáticamente.
        """
        print("La reproducción de audio se maneja automáticamente")
        
        # Si tenemos una implementación fallback, intentar reproducir directamente
        if not WEBRTC_AVAILABLE and hasattr(self.webrtc, 'stream_out') and self.webrtc.stream_out:
            try:
                self.webrtc.stream_out.write(audio_data)
                return True
            except Exception as e:
                print(f"❌ Error reproduciendo audio en fallback: {e}")
                return False
                
        return False
    
    def test_audio_output(self):
        """
        Prueba la salida de audio reproduciendo un tono
        """
        print("🔊 Generando tono de prueba...")
        
        # Si es WebRTC real, generar y enviar un tono
        if WEBRTC_AVAILABLE:
            try:
                # Generar tono de prueba (440 Hz)
                duration = 0.5  # segundos
                frequency = 440.0  # Hz
                sample_rate = 48000
                
                # Generar muestras
                samples = (duration * sample_rate)
                t = np.linspace(0, duration, int(samples), False)
                tone = np.sin(frequency * t * 2 * np.pi)
                
                # Convertir a formato adecuado
                audio_data = (tone * 32767).astype(np.int16)
                
                # Añadir a la pista de audio
                if hasattr(self.webrtc, 'mic_track'):
                    self.webrtc.mic_track.add_audio(audio_data)
                    print("✅ Tono de prueba enviado a WebRTC")
                    return True
                else:
                    print("❌ No hay pista de micrófono disponible")
                    return False
                
            except Exception as e:
                print(f"❌ Error al generar tono de prueba WebRTC: {e}")
                return False
                
        # Si es Fallback, usar su método de prueba
        elif hasattr(self.webrtc, 'test_audio_output'):
            return self.webrtc.test_audio_output()
            
        # Si no hay ninguna opción disponible
        else:
            print("❌ No hay mecanismo disponible para prueba de audio")
            return False
    
    def on_voice_data(self, data):
        """
        Compatibilidad con el manejador de eventos anterior
        """
        try:
            username = data.get('username', 'Unknown')
            audio_data = data.get('data')
            
            print(f"📥 Procesando datos de audio de {username}")
            
            # Agregar los datos al webrtc si está disponible
            if hasattr(self.webrtc, 'add_audio_data') and audio_data:
                self.webrtc.add_audio_data(audio_data)
            
        except Exception as e:
            print(f"❌ Error procesando datos de voz: {e}")
            import traceback
            traceback.print_exc() 