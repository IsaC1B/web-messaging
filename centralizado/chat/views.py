"""
Vistas de la app de chat.
"""

from django.shortcuts import render
from django.conf import settings


def chat_room(request):
    """Renderiza la página principal del chat."""
    ws_host = request.get_host()
    context = {
        "ws_url": f"ws://{ws_host}/ws/chat/",
    }
    return render(request, "chat/index.html", context)
