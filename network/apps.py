from django.apps import AppConfig
import threading
import asyncio
import os
import network.node_singleton as singleton
from .p2p_node import P2PNode


class NetworkConfig(AppConfig):
    name = 'network'

    def ready(self):
        if os.environ.get('RUN_MAIN') != 'true':
            return

        def start_node():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            host = os.environ.get("P2P_HOST", "0.0.0.0")
            port = int(os.environ.get("P2P_PORT", 12345))

            peers_env = os.environ.get("P2P_PEERS", "")
            peers = [p.strip() for p in peers_env.split(",") if p.strip()]

            node = P2PNode(host, port, peers=peers)
            node.loop = loop  

            singleton.node_instance = node

            loop.run_until_complete(node.start())

        thread = threading.Thread(target=start_node, daemon=True)
        thread.start()


def start_node():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    host = os.environ.get("P2P_HOST", "0.0.0.0")
    port = int(os.environ.get("P2P_PORT", 12345))

    peers_env = os.environ.get("P2P_PEERS", "")
    peers = [p.strip() for p in peers_env.split(",") if p.strip()]

    node = P2PNode(host, port, peers=peers)
    node.loop = loop  

    singleton.node_instance = node

    loop.run_until_complete(node.start())