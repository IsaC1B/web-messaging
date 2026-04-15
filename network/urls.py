from django.urls import path
from .views import index, connect_peer, send_to, get_messages, get_nodes, send_signal, poll_signals

urlpatterns = [
    path('', index),
    path('connect/', connect_peer),
    path('send/', send_to),
    path('messages/', get_messages),
    path('nodes/', get_nodes),
    path('signal/send/', send_signal),
    path('signal/poll/', poll_signals),
]