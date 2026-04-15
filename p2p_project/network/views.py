from django.shortcuts import render
from django.http import JsonResponse
from . import node_singleton
import asyncio


def index(request):
    node = node_singleton.node_instance
    if node is None:
        return render(request, "index.html", {
            "nodes": {}, "messages": [], "error": "Nodo aún no iniciado"
        })
    return render(request, "index.html", {
        "nodes": node.known_nodes,
        "messages": node.messages,
        "node_id": node.node_id
    })


def connect_peer(request):
    node = node_singleton.node_instance
    peer = request.GET.get("peer")
    if node is None:
        return JsonResponse({"error": "Nodo no iniciado"}, status=500)
    if not peer:
        return JsonResponse({"error": "Falta peer"}, status=400)
    try:
        future = asyncio.run_coroutine_threadsafe(
            node.connect_to_new_peer(peer), node.loop
        )
        result = future.result(timeout=5)
    except TimeoutError:
        return JsonResponse({"error": "Timeout"}, status=504)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse(result)


def send_to(request):
    """Envía mensaje directo a un nodo específico."""
    node = node_singleton.node_instance
    target = request.GET.get("target")   # node_id destino: host:port
    text = request.GET.get("text")

    if node is None:
        return JsonResponse({"error": "Nodo no iniciado"}, status=500)
    if not target or not text:
        return JsonResponse({"error": "Faltan parámetros target y text"}, status=400)

    try:
        future = asyncio.run_coroutine_threadsafe(
            node.send_to(target, text), node.loop
        )
        result = future.result(timeout=5)
    except TimeoutError:
        return JsonResponse({"error": "Timeout"}, status=504)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    if not result["ok"]:
        return JsonResponse(result, status=503)
    return JsonResponse(result)


def get_messages(request):
    node = node_singleton.node_instance
    target = request.GET.get("target")
    if node is None:
        return JsonResponse({"messages": []})

    msgs = node.messages
    if target:
        msgs = [
            m for m in msgs
            if m.get("from") == target or m.get("to") == target
        ]
    return JsonResponse({"messages": msgs})


def get_nodes(request):
    """Lista de nodos activos para la UI"""
    node = node_singleton.node_instance
    if node is None:
        return JsonResponse({"nodes": {}})
    return JsonResponse({"nodes": node.known_nodes})