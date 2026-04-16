"""
ASGI config for p2p_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

'''import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'p2p_project.settings')

application = get_asgi_application()
'''

import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path
from network import consumers

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'p2p_project.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path("ws/call/<str:room_id>/", consumers.CallConsumer.as_asgi()),
    ]),
})