"""
Consumer WebSocket para el chat.
Maneja conexiones, desconexiones, chat general, chat privado y grupos.
"""

import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer


# ── Estado global ─────────────────────────────────────────────────────────────
# {channel_name: username}
connected_users: dict = {}

# {username: channel_name}  — inverso para envíos directos
user_channels: dict = {}

# {group_name: set(channel_names)}
groups: dict = {}

# {group_name: username}  — quién creó el grupo
group_owners: dict = {}

# {channel_name: username}  — quién está escribiendo
typing_users: dict = {}
# ──────────────────────────────────────────────────────────────────────────────


class ChatConsumer(AsyncWebsocketConsumer):
    """Consumer que maneja todos los tipos de chat via WebSocket."""

    GENERAL_GROUP = "chat_general"

    # ── Conexión / desconexión ─────────────────────────────────────────────

    async def connect(self):
        await self.channel_layer.group_add(self.GENERAL_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        username = connected_users.pop(self.channel_name, None)
        user_channels.pop(username, None)

        await self.channel_layer.group_discard(self.GENERAL_GROUP, self.channel_name)

        for gname, members in list(groups.items()):
            if self.channel_name in members:
                members.discard(self.channel_name)
                if members:
                    await self.channel_layer.group_send(
                        f"group_{gname}",
                        {
                            "type": "system_message",
                            "content": f"🔴 {username} abandonó el grupo «{gname}»",
                            "timestamp": self._ts(),
                            "group_name": gname,
                        },
                    )
                    await self._broadcast_group_members(gname)
                else:
                    del groups[gname]
                    group_owners.pop(gname, None)
                await self.channel_layer.group_discard(f"group_{gname}", self.channel_name)

        if username:
            await self.channel_layer.group_send(
                self.GENERAL_GROUP,
                {
                    "type": "system_message",
                    "content": f"🔴 {username} ha abandonado el chat",
                    "timestamp": self._ts(),
                },
            )
            await self._broadcast_user_list()
            await self._broadcast_group_list()

    # ── Recepción de mensajes ──────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")

        if msg_type == "join":
            await self._handle_join(data)
        elif msg_type == "message":
            await self._handle_general_message(data)
        elif msg_type == "private_message":
            await self._handle_private_message(data)
        elif msg_type == "create_group":
            await self._handle_create_group(data)
        elif msg_type == "join_group":
            await self._handle_join_group(data)
        elif msg_type == "leave_group":
            await self._handle_leave_group(data)
        elif msg_type == "group_message":
            await self._handle_group_message(data)
        elif msg_type == "typing":
            await self._handle_typing(data)
        elif msg_type == "ping":
            await self._handle_ping(data)

    # ── Handlers de lógica ────────────────────────────────────────────────

    async def _handle_join(self, data):
        username = data.get("username", "Anónimo").strip()[:30]

        if username in user_channels:
            await self.send(text_data=json.dumps({
                "type": "error",
                "content": f"El nombre «{username}» ya está en uso. Elige otro.",
            }))
            await self.close()
            return

        connected_users[self.channel_name] = username
        user_channels[username] = self.channel_name

        await self.send(text_data=json.dumps({
            "type": "system",
            "content": f"¡Bienvenido al chat, {username}!",
            "timestamp": self._ts(),
        }))

        await self.channel_layer.group_send(
            self.GENERAL_GROUP,
            {
                "type": "system_message",
                "content": f"🟢 {username} se ha unido al chat",
                "timestamp": self._ts(),
            },
        )
        await self._broadcast_user_list()
        await self._broadcast_group_list()

    async def _handle_general_message(self, data):
        username = connected_users.get(self.channel_name, "???")
        content = data.get("content", "").strip()
        if not content:
            return

        await self.channel_layer.group_send(
            self.GENERAL_GROUP,
            {
                "type": "chat_message",
                "username": username,
                "content": content,
                "timestamp": self._ts(),
                "sender_channel": self.channel_name,
                "chat_context": "general",
            },
        )

    async def _handle_private_message(self, data):
        sender = connected_users.get(self.channel_name, "???")
        target = data.get("target", "").strip()
        content = data.get("content", "").strip()

        if not content:
            return

        target_channel = user_channels.get(target)
        if not target_channel:
            await self.send(text_data=json.dumps({
                "type": "error",
                "content": f"El usuario «{target}» no está conectado.",
            }))
            return

        payload = {
            "sender": sender,
            "target": target,
            "content": content,
            "timestamp": self._ts(),
        }

        await self.channel_layer.send(target_channel, {
            "type": "private_message_event",
            **payload,
            "is_own": False,
        })
        await self.send(text_data=json.dumps({
            "type": "private_msg",
            **payload,
            "is_own": True,
        }))

    async def _handle_create_group(self, data):
        username = connected_users.get(self.channel_name, "???")
        gname = data.get("group_name", "").strip()[:40]

        if not gname:
            await self._send_error("El nombre del grupo no puede estar vacío.")
            return

        if gname in groups:
            await self._send_error(f"El grupo «{gname}» ya existe.")
            return

        groups[gname] = {self.channel_name}
        group_owners[gname] = username
        await self.channel_layer.group_add(f"group_{gname}", self.channel_name)

        await self.send(text_data=json.dumps({
            "type": "group_joined",
            "group_name": gname,
            "members": [username],
            "timestamp": self._ts(),
        }))

        await self.channel_layer.group_send(
            f"group_{gname}",
            {
                "type": "system_message",
                "content": f"🏠 Grupo «{gname}» creado por {username}",
                "timestamp": self._ts(),
                "group_name": gname,
            },
        )
        await self._broadcast_group_list()

    async def _handle_join_group(self, data):
        username = connected_users.get(self.channel_name, "???")
        gname = data.get("group_name", "").strip()

        if gname not in groups:
            await self._send_error(f"El grupo «{gname}» no existe.")
            return

        if self.channel_name in groups[gname]:
            await self._send_error(f"Ya estás en el grupo «{gname}».")
            return

        groups[gname].add(self.channel_name)
        await self.channel_layer.group_add(f"group_{gname}", self.channel_name)

        members = [connected_users.get(ch, "???") for ch in groups[gname]]

        await self.send(text_data=json.dumps({
            "type": "group_joined",
            "group_name": gname,
            "members": members,
            "timestamp": self._ts(),
        }))

        await self.channel_layer.group_send(
            f"group_{gname}",
            {
                "type": "system_message",
                "content": f"🟢 {username} se unió al grupo «{gname}»",
                "timestamp": self._ts(),
                "group_name": gname,
            },
        )
        await self._broadcast_group_members(gname)

    async def _handle_leave_group(self, data):
        username = connected_users.get(self.channel_name, "???")
        gname = data.get("group_name", "").strip()

        if gname not in groups or self.channel_name not in groups[gname]:
            return

        groups[gname].discard(self.channel_name)
        await self.channel_layer.group_discard(f"group_{gname}", self.channel_name)

        await self.send(text_data=json.dumps({
            "type": "group_left",
            "group_name": gname,
        }))

        if groups[gname]:
            await self.channel_layer.group_send(
                f"group_{gname}",
                {
                    "type": "system_message",
                    "content": f"🔴 {username} abandonó el grupo «{gname}»",
                    "timestamp": self._ts(),
                    "group_name": gname,
                },
            )
            await self._broadcast_group_members(gname)
        else:
            del groups[gname]
            group_owners.pop(gname, None)
            await self._broadcast_group_list()

    async def _handle_group_message(self, data):
        username = connected_users.get(self.channel_name, "???")
        gname = data.get("group_name", "").strip()
        content = data.get("content", "").strip()

        if not content:
            return

        if gname not in groups or self.channel_name not in groups[gname]:
            await self._send_error(f"No perteneces al grupo «{gname}».")
            return

        await self.channel_layer.group_send(
            f"group_{gname}",
            {
                "type": "chat_message",
                "username": username,
                "content": content,
                "timestamp": self._ts(),
                "sender_channel": self.channel_name,
                "chat_context": "group",
                "group_name": gname,
            },
        )

    # ── Handlers de eventos de canal ──────────────────────────────────────

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "username": event["username"],
            "content": event["content"],
            "timestamp": event["timestamp"],
            "is_own": event["sender_channel"] == self.channel_name,
            "chat_context": event.get("chat_context", "general"),
            "group_name": event.get("group_name"),
        }))

    async def system_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "system",
            "content": event["content"],
            "timestamp": event["timestamp"],
            "group_name": event.get("group_name"),
        }))

    async def user_list_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_list",
            "users": event["users"],
        }))

    async def group_list_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "group_list",
            "groups": event["groups"],
        }))

    async def group_members_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "group_members",
            "group_name": event["group_name"],
            "members": event["members"],
        }))

    async def private_message_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "private_msg",
            "sender": event["sender"],
            "target": event["target"],
            "content": event["content"],
            "timestamp": event["timestamp"],
            "is_own": event.get("is_own", False),
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing",
            "username": event["username"],
            "is_typing": event["is_typing"],
        }))

    async def ping_response(self, event):
        await self.send(text_data=json.dumps({
            "type": "pong",
            "timestamp": event["timestamp"],
        }))

    # ── Handlers de lógica (typing y ping) ──────────────────────────────────

    async def _handle_typing(self, data):
        """Notificar a otros usuarios que estamos escribiendo."""
        username = connected_users.get(self.channel_name, "???")
        is_typing = data.get("is_typing", False)
        
        if is_typing:
            typing_users[self.channel_name] = username
        else:
            typing_users.pop(self.channel_name, None)
        
        await self.channel_layer.group_send(
            self.GENERAL_GROUP,
            {
                "type": "typing_indicator",
                "username": username,
                "is_typing": is_typing,
            },
        )

    async def _handle_ping(self, data):
        """Responder a un ping para medir latencia."""
        timestamp = data.get("timestamp")
        await self.send(text_data=json.dumps({
            "type": "pong",
            "timestamp": timestamp,
        }))

    # ── Utilidades ─────────────────────────────────────────────────────────

    async def _send_error(self, msg):
        await self.send(text_data=json.dumps({"type": "error", "content": msg}))

    async def _broadcast_user_list(self):
        users = list(connected_users.values())
        await self.channel_layer.group_send(
            self.GENERAL_GROUP,
            {"type": "user_list_update", "users": users},
        )

    async def _broadcast_group_list(self):
        group_info = [
            {
                "name": gname,
                "owner": group_owners.get(gname, ""),
                "count": len(members),
            }
            for gname, members in groups.items()
        ]
        await self.channel_layer.group_send(
            self.GENERAL_GROUP,
            {"type": "group_list_update", "groups": group_info},
        )

    async def _broadcast_group_members(self, gname):
        if gname not in groups:
            return
        members = [connected_users.get(ch, "???") for ch in groups[gname]]
        await self.channel_layer.group_send(
            f"group_{gname}",
            {"type": "group_members_update", "group_name": gname, "members": members},
        )

    @staticmethod
    def _ts():
        return datetime.now().strftime("%H:%M:%S")
