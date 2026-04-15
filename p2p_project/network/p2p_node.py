import asyncio
import websockets
import json
import random
import socket
import struct

BROADCAST_PORT = 12345
MULTICAST_GROUP = '224.0.0.1'  

class P2PNode:
    def __init__(self, host, port, peers=None):
        self.host = host
        self.port = port
        self.peers = peers if peers else []
        self.connections = {}
        self.connected_peers = set()
        real_ip = socket.gethostbyname(socket.gethostname())
        self.node_id = f"{real_ip}:{port}"
        self.known_nodes = {}
        self.messages = []
        self.loop = None

    def get_load(self):
        return random.randint(1, 100)

    async def handler(self, websocket):
        node_id = None
        try:
            async for message in websocket:
                data = json.loads(message)
                node_id = data.get("node_id")
                if node_id:
                    self.connections[node_id] = websocket
                await self.process_message(data)
        finally:
            if node_id and self.connections.get(node_id) is websocket:
                del self.connections[node_id]

    async def process_message(self, data):
        msg_type = data.get("type", "status")

        if msg_type == "status":
            node_id = data["node_id"]
            self.known_nodes[node_id] = data

        elif msg_type == "chat":
            self.messages.append({
                "from": data["from"],
                "to": self.node_id,     
                "text": data["text"],
                "direction": "received"
            })

    async def connect_to_new_peer(self, peer_url):
        if peer_url in self.connected_peers:
            return {"ok": True}

        try:
            ws = await websockets.connect(peer_url)
            # extraer node_id del URL: ws://host:port → host:port
            peer_id = peer_url.replace("ws://", "")
            self.connections[peer_id] = ws
            self.connected_peers.add(peer_url)
            self.peers.append(peer_url)
            asyncio.create_task(self.listen(ws, peer_id))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def listen(self, websocket, peer_id):
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_message(data)
        except:
            pass
        finally:
            # limpiar si se cae la conexión
            self.connections.pop(peer_id, None)
            ws_url = f"ws://{peer_id}"
            self.connected_peers.discard(ws_url)
            self.known_nodes.pop(peer_id, None)

    async def send_to(self, target_node_id, text):
        ws = self.connections.get(target_node_id)

        if not ws:
            # intentar conectar primero
            ws_url = f"ws://{target_node_id}"
            result = await self.connect_to_new_peer(ws_url)
            if not result["ok"]:
                return {"ok": False, "error": f"Nodo {target_node_id} no disponible"}
            ws = self.connections.get(target_node_id)

        try:
            message = json.dumps({
                "type": "chat",
                "from": self.node_id,
                "to": target_node_id,
                "text": text
            })
            await ws.send(message)
            self.messages.append({
                "from": self.node_id,
                "to": target_node_id,
                "text": text,
                "direction": "sent"
            })
            return {"ok": True}
        except Exception as e:
            # nodo caído: limpiar y notificar
            self.connections.pop(target_node_id, None)
            self.connected_peers.discard(f"ws://{target_node_id}")
            self.known_nodes.pop(target_node_id, None)
            return {"ok": False, "error": f"Nodo {target_node_id} caído, mensaje descartado"}


    async def send_status(self):
        while True:
            message = json.dumps({
                "type": "status",
                "node_id": self.node_id,
                "load": self.get_load(),
                "hostname": socket.gethostname(),
                "ws_url": f"ws://{self.node_id}"
            })
            dead = []
            for nid, ws in list(self.connections.items()):
                try:
                    await ws.send(message)
                except:
                    dead.append(nid)
            for nid in dead:
                self.connections.pop(nid, None)
                self.known_nodes.pop(nid, None)
            await asyncio.sleep(2)

    async def udp_broadcast(self):
        """Anuncia este nodo en la red vía multicast UDP cada 3 segundos."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)  # TTL para cruzar routers si es necesario
        sock.setblocking(False)

        payload = json.dumps({
            "type": "discovery",
            "node_id": self.node_id,
            "ws_url": f"ws://{self.node_id}",
            "hostname": socket.gethostname()
        }).encode()

        loop = asyncio.get_event_loop()
        while True:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: sock.sendto(payload, (MULTICAST_GROUP, BROADCAST_PORT))
                )
            except:
                pass
            await asyncio.sleep(3)

    async def udp_listener(self):
        """Escucha multicast UDP de otros nodos y los registra."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Unirse al grupo multicast
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, 
                        struct.pack("4s4s", socket.inet_aton(MULTICAST_GROUP), socket.inet_aton("0.0.0.0")))
        sock.bind(("", BROADCAST_PORT))
        sock.setblocking(False)

        loop = asyncio.get_event_loop()
        while True:
            try:
                data, addr = await loop.run_in_executor(None, lambda: sock.recvfrom(1024))
                msg = json.loads(data.decode())

                if msg.get("type") == "discovery":
                    node_id = msg["node_id"]
                    if node_id != self.node_id:  
                        self.known_nodes[node_id] = {
                            "node_id": node_id,
                            "ws_url": msg["ws_url"],
                            "hostname": msg["hostname"],
                            "load": "?",
                            "discovered_via": "multicast"
                        }
            except:
                await asyncio.sleep(0.1)


    async def connect_to_peers(self):
        for peer in self.peers:
            await self.connect_to_new_peer(peer)

    async def start(self):
        server = await websockets.serve(self.handler, self.host, self.port)
        await self.connect_to_peers()
        await asyncio.gather(
            self.send_status(),
            self.udp_broadcast(),
            self.udp_listener(),
            server.wait_closed()
        )