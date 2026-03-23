"""
Consumer WebSocket para el chat.
Maneja conexiones, desconexiones, y broadcast de mensajes.
"""

import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer


# Registro global de usuarios conectados: {channel_name: username}
connected_users = {}


class ChatConsumer(AsyncWebsocketConsumer):
    """Consumer que maneja la sala de chat WebSocket."""

    ROOM_GROUP = "chat_room"

    async def connect(self):
        """Se ejecuta cuando un cliente WebSocket se conecta."""
        await self.channel_layer.group_add(self.ROOM_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        """Se ejecuta cuando un cliente WebSocket se desconecta."""
        username = connected_users.pop(self.channel_name, None)

        await self.channel_layer.group_discard(self.ROOM_GROUP, self.channel_name)

        if username:
            # Notificar a todos que el usuario se fue
            await self.channel_layer.group_send(
                self.ROOM_GROUP,
                {
                    "type": "system_message",
                    "content": f"🔴 {username} ha abandonado el chat",
                    "timestamp": self._timestamp(),
                },
            )
            # Actualizar lista de usuarios
            await self._broadcast_user_list()

    async def receive(self, text_data):
        """Se ejecuta cuando se recibe un mensaje del cliente."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")

        if msg_type == "join":
            username = data.get("username", "Anónimo")
            connected_users[self.channel_name] = username

            # Mensaje de bienvenida privado
            await self.send(text_data=json.dumps({
                "type": "system",
                "content": f"¡Bienvenido al chat, {username}!",
                "timestamp": self._timestamp(),
            }))

            # Notificar a todos
            await self.channel_layer.group_send(
                self.ROOM_GROUP,
                {
                    "type": "system_message",
                    "content": f"🟢 {username} se ha unido al chat",
                    "timestamp": self._timestamp(),
                },
            )
            await self._broadcast_user_list()

        elif msg_type == "message":
            username = connected_users.get(self.channel_name, "???")
            content = data.get("content", "")

            await self.channel_layer.group_send(
                self.ROOM_GROUP,
                {
                    "type": "chat_message",
                    "username": username,
                    "content": content,
                    "timestamp": self._timestamp(),
                    "sender_channel": self.channel_name,
                },
            )

    # ── Handlers de grupo ──────────────────────────────────

    async def chat_message(self, event):
        """Envía un mensaje de chat a este cliente."""
        await self.send(text_data=json.dumps({
            "type": "message",
            "username": event["username"],
            "content": event["content"],
            "timestamp": event["timestamp"],
            "is_own": event["sender_channel"] == self.channel_name,
        }))

    async def system_message(self, event):
        """Envía un mensaje de sistema a este cliente."""
        await self.send(text_data=json.dumps({
            "type": "system",
            "content": event["content"],
            "timestamp": event["timestamp"],
        }))

    async def user_list_update(self, event):
        """Envía la lista actualizada de usuarios."""
        await self.send(text_data=json.dumps({
            "type": "user_list",
            "users": event["users"],
        }))

    # ── Utilidades ─────────────────────────────────────────

    async def _broadcast_user_list(self):
        """Envía la lista de usuarios a todo el grupo."""
        users = list(connected_users.values())
        await self.channel_layer.group_send(
            self.ROOM_GROUP,
            {
                "type": "user_list_update",
                "users": users,
            },
        )

    @staticmethod
    def _timestamp():
        return datetime.now().strftime("%H:%M:%S")
