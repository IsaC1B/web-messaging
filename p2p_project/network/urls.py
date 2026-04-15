from django.urls import path
from .views import index, connect_peer, send_to, get_messages, get_nodes

urlpatterns = [
    path('', index),
    path('connect/', connect_peer),
    path('send/', send_to),
    path('messages/', get_messages),
    path('nodes/', get_nodes),
]