"""
Cliente WebSocket para Chat — Funciones de Base
Conexión, envío y recepción de mensajes del servidor Django + Channels.

CONFIGURACIÓN:
  SERVER_HOST = "10.253.0.236"  (cambiar IP/localhost según corresponda)
  SERVER_PORT = 8000            (puerto del servidor)
"""

import asyncio
import websockets
import json
import time
from typing import Callable, Optional, Dict, Any


SERVER_HOST = "10.253.0.236"
SERVER_PORT = 8000
WS_URI = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/chat/"


class WebSocketChatClient:
    """Cliente WebSocket para interactuar con el servidor de chat."""

    def __init__(self, username: str, message_callback: Optional[Callable] = None):
        """
        Inicializa el cliente.
        
        Args:
            username: Nombre del usuario
            message_callback: Función que se llama al recibir mensajes
        """
        self.username = username
        self.websocket = None
        self.running = False
        self.message_callback = message_callback
        self.last_ping_time = None
        self.latency_ms = 0

    async def connect(self):
        """Conecta al servidor WebSocket y mantiene la conexión activa."""
        try:
            async with websockets.connect(WS_URI) as ws:
                self.websocket = ws
                self.running = True
                
                # Envía el join
                await self.send_message({"type": "join", "username": self.username})
                
                # Tarea de ping periódico
                ping_task = asyncio.create_task(self._ping_loop())
                
                try:
                    # Recibe mensajes
                    async for raw_msg in ws:
                        data = json.loads(raw_msg)
                        self._handle_message(data)
                finally:
                    ping_task.cancel()
                    self.running = False
                    
        except (ConnectionRefusedError, OSError) as e:
            print(f"❌ Error de conexión: {e}")
            self.running = False
        except websockets.ConnectionClosed:
            print("⚠️ Conexión cerrada")
            self.running = False

    async def send_message(self, data: Dict[str, Any]):
        """Envía un mensaje al servidor."""
        if self.websocket and self.running:
            msg = json.dumps(data)
            await self.websocket.send(msg)

    async def send_chat_message(self, content: str):
        """Envía un mensaje de chat."""
        await self.send_message({
            "type": "message",
            "content": content
        })

    async def send_typing(self, is_typing: bool):
        """Notifica si el usuario está escribiendo."""
        await self.send_message({
            "type": "typing",
            "is_typing": is_typing
        })

    async def send_ping(self):
        """Envía un ping para medir latencia."""
        self.last_ping_time = time.time()
        await self.send_message({
            "type": "ping",
            "timestamp": self.last_ping_time
        })

    async def _ping_loop(self):
        """Envía pings cada 3 segundos."""
        try:
            while self.running:
                await asyncio.sleep(3)
                if self.running:
                    await self.send_ping()
        except asyncio.CancelledError:
            pass

    def _handle_message(self, data: Dict[str, Any]):
        """Procesa mensajes del servidor."""
        msg_type = data.get("type")

        if msg_type == "pong":
            if self.last_ping_time:
                self.latency_ms = int((time.time() - self.last_ping_time) * 1000)
                print(f"📡 Latencia: {self.latency_ms}ms")

        elif msg_type == "typing":
            status = "escribiendo" if data.get("is_typing") else "paró"
            print(f"✍️ {data.get('username')} {status}")

        if self.message_callback:
            self.message_callback(data)

    async def disconnect(self):
        """Desconecta del servidor."""
        self.running = False
        if self.websocket:
            await self.websocket.close()

    def get_latency(self) -> int:
        """Retorna la latencia actual en ms."""
        return self.latency_ms


async def main():
    """Ejemplo de uso."""
    
    def on_message(data):
        print(f"📨 {data}")
    
    client = WebSocketChatClient("TestUser", message_callback=on_message)
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        print("\n👋 Desconectando...")
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
