"""
Cliente de Chat WebSocket (Python)
Se conecta al servidor Django Channels.
Configura SERVER_HOST y SERVER_PORT abajo.
"""

import asyncio
import websockets
import json
import threading
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime

# ============================================================
# CONFIGURACIÓN - Definir IP y Puerto del servidor
# ============================================================
SERVER_HOST = "localhost"  # IP del servidor Django
SERVER_PORT = 8766         # Puerto del servidor Django
# ============================================================

WS_URI = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/chat/"


class ChatClient:
    """Cliente de chat con interfaz gráfica usando tkinter."""

    def __init__(self):
        self.websocket = None
        self.loop = None
        self.running = False
        self.username = None

        # ── Ventana principal ──────────────────────────────
        self.root = tk.Tk()
        self.root.title(" Chat WebSocket - Cliente Python")
        self.root.geometry("800x600")
        self.root.minsize(650, 450)
        self.root.configure(bg="#0f0f23")

        # Colores del tema
        self.BG = "#0f0f23"
        self.BG2 = "#1a1a35"
        self.BG_INPUT = "#1e1e3a"
        self.FG = "#e8e8f0"
        self.FG_DIM = "#6b6b8d"
        self.ACCENT = "#e94560"
        self.ACCENT2 = "#6c63ff"
        self.GREEN = "#2ecc71"
        self.BLUE = "#3b82f6"

        # Iniciar con pantalla de login
        self._build_login_screen()

    # ── Pantalla de Login ──────────────────────────────────
    def _build_login_screen(self):
        self.login_frame = tk.Frame(self.root, bg=self.BG)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            self.login_frame, text="💬", font=("Segoe UI Emoji", 48),
            bg=self.BG, fg=self.FG
        ).pack(pady=(0, 5))

        tk.Label(
            self.login_frame, text="Chat WebSocket",
            font=("Segoe UI", 24, "bold"), bg=self.BG, fg=self.FG
        ).pack(pady=(0, 5))

        tk.Label(
            self.login_frame, text=f"Cliente Python → {WS_URI}",
            font=("Segoe UI", 10), bg=self.BG, fg=self.FG_DIM
        ).pack(pady=(0, 20))

        tk.Label(
            self.login_frame, text="Tu nombre de usuario:",
            font=("Segoe UI", 12), bg=self.BG, fg=self.FG
        ).pack(pady=(0, 5))

        self.username_entry = tk.Entry(
            self.login_frame, font=("Segoe UI", 14), width=25,
            justify="center", bg=self.BG_INPUT, fg=self.FG,
            insertbackground=self.FG, relief="flat", bd=0,
            highlightthickness=2, highlightcolor=self.ACCENT,
            highlightbackground=self.ACCENT2
        )
        self.username_entry.pack(pady=(0, 15), ipady=8)
        self.username_entry.focus_set()
        self.username_entry.bind("<Return>", lambda e: self._connect())

        self.connect_btn = tk.Button(
            self.login_frame, text="Conectarse",
            font=("Segoe UI", 13, "bold"),
            bg=self.ACCENT, fg="white", activebackground="#c0392b",
            activeforeground="white", relief="flat", cursor="hand2",
            padx=30, pady=8, command=self._connect
        )
        self.connect_btn.pack(pady=(0, 10))

        self.status_label = tk.Label(
            self.login_frame, text="",
            font=("Segoe UI", 10), bg=self.BG, fg=self.FG_DIM
        )
        self.status_label.pack()

    # ── Pantalla de Chat ───────────────────────────────────
    def _build_chat_screen(self):
        self.login_frame.destroy()

        # Header
        header = tk.Frame(self.root, bg=self.ACCENT, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text=f" Chat WebSocket  —  {self.username}",
            font=("Segoe UI", 14, "bold"), bg=self.ACCENT, fg="white"
        ).pack(side="left", padx=15, pady=10)

        tk.Label(
            header, text=f" Cliente Python  |  🔗 {WS_URI}",
            font=("Segoe UI", 9), bg=self.ACCENT, fg="#ffcccc"
        ).pack(side="right", padx=15, pady=10)

        # Contenido principal
        content = tk.Frame(self.root, bg=self.BG)
        content.pack(fill="both", expand=True, padx=8, pady=8)

        # Panel de mensajes
        msg_frame = tk.Frame(content, bg=self.BG)
        msg_frame.pack(side="left", fill="both", expand=True)

        self.chat_display = scrolledtext.ScrolledText(
            msg_frame, wrap=tk.WORD, state="disabled",
            font=("Consolas", 11), bg=self.BG2, fg=self.FG,
            relief="flat", bd=0, padx=12, pady=12,
            insertbackground=self.FG, selectbackground=self.ACCENT2
        )
        self.chat_display.pack(fill="both", expand=True)

        self.chat_display.tag_config("system", foreground="#f39c12",
                                     font=("Consolas", 10, "italic"))
        self.chat_display.tag_config("username", foreground=self.BLUE,
                                     font=("Consolas", 11, "bold"))
        self.chat_display.tag_config("own_username", foreground=self.GREEN,
                                     font=("Consolas", 11, "bold"))
        self.chat_display.tag_config("timestamp", foreground=self.FG_DIM,
                                     font=("Consolas", 9))
        self.chat_display.tag_config("message", foreground=self.FG,
                                     font=("Consolas", 11))

        # Panel de usuarios
        users_panel = tk.Frame(content, bg=self.BG_INPUT, width=180)
        users_panel.pack(side="right", fill="y", padx=(8, 0))
        users_panel.pack_propagate(False)

        tk.Label(
            users_panel, text="👥 En Línea",
            font=("Segoe UI", 12, "bold"), bg=self.BG_INPUT, fg=self.FG
        ).pack(pady=(12, 8), padx=10, anchor="w")

        sep = tk.Frame(users_panel, bg=self.ACCENT, height=2)
        sep.pack(fill="x", padx=10, pady=(0, 8))

        self.users_listbox = tk.Listbox(
            users_panel, font=("Segoe UI", 11), bg=self.BG_INPUT,
            fg=self.FG, relief="flat", bd=0, highlightthickness=0,
            selectbackground=self.ACCENT2, activestyle="none"
        )
        self.users_listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Barra de entrada
        input_frame = tk.Frame(self.root, bg=self.BG2, height=55)
        input_frame.pack(fill="x", padx=8, pady=(0, 8))
        input_frame.pack_propagate(False)

        self.msg_entry = tk.Entry(
            input_frame, font=("Segoe UI", 13), bg=self.BG_INPUT,
            fg=self.FG, insertbackground=self.FG, relief="flat", bd=0,
            highlightthickness=2, highlightcolor=self.ACCENT,
            highlightbackground=self.ACCENT2
        )
        self.msg_entry.pack(side="left", fill="both", expand=True,
                            padx=(10, 8), pady=10, ipady=5)
        self.msg_entry.bind("<Return>", lambda e: self._send_message())
        self.msg_entry.focus_set()

        self.send_btn = tk.Button(
            input_frame, text="Enviar ➤",
            font=("Segoe UI", 12, "bold"),
            bg=self.ACCENT, fg="white", activebackground="#c0392b",
            activeforeground="white", relief="flat", cursor="hand2",
            padx=20, command=self._send_message
        )
        self.send_btn.pack(side="right", padx=(0, 10), pady=10)

    # ── Lógica de conexión ─────────────────────────────────
    def _connect(self):
        self.username = self.username_entry.get().strip()
        if not self.username:
            self.status_label.config(text="⚠️ Ingresa un nombre de usuario",
                                     fg=self.ACCENT)
            return

        self.status_label.config(text="Conectando...", fg=self.FG_DIM)
        self.connect_btn.config(state="disabled")

        self.running = True
        thread = threading.Thread(target=self._run_async_loop, daemon=True)
        thread.start()

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._ws_handler())
        except Exception as exc:
            error_msg = str(exc)
            self.root.after(0, lambda m=error_msg: self._on_connection_error(m))

    async def _ws_handler(self):
        try:
            async with websockets.connect(WS_URI) as ws:
                self.websocket = ws

                join_msg = json.dumps({
                    "type": "join",
                    "username": self.username
                })
                await ws.send(join_msg)

                self.root.after(0, self._build_chat_screen)

                async for raw in ws:
                    data = json.loads(raw)
                    self.root.after(0, lambda d=data: self._handle_message(d))

        except (ConnectionRefusedError, OSError):
            raise Exception(f"No se pudo conectar a {WS_URI}")
        except websockets.ConnectionClosed:
            self.root.after(0, lambda: self._append_system(
                " Conexión perdida con el servidor"))
        finally:
            self.running = False

    def _on_connection_error(self, error_msg):
        self.status_label.config(text=f" {error_msg}", fg=self.ACCENT)
        self.connect_btn.config(state="normal")

    # ── Manejo de mensajes ─────────────────────────────────
    def _handle_message(self, data):
        msg_type = data.get("type")

        if msg_type == "system":
            self._append_system(data.get("content", ""),
                                data.get("timestamp", ""))
        elif msg_type == "message":
            username = data.get("username", "???")
            content = data.get("content", "")
            ts = data.get("timestamp", "")
            is_own = data.get("is_own", False)
            self._append_chat(username, content, ts, is_own)
        elif msg_type == "user_list":
            self._update_user_list(data.get("users", []))

    def _append_system(self, content, ts=""):
        self.chat_display.config(state="normal")
        if ts:
            self.chat_display.insert("end", f"[{ts}] ", "timestamp")
        self.chat_display.insert("end", f"{content}\n", "system")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _append_chat(self, username, content, ts="", is_own=False):
        self.chat_display.config(state="normal")
        if ts:
            self.chat_display.insert("end", f"[{ts}] ", "timestamp")
        tag = "own_username" if is_own else "username"
        self.chat_display.insert("end", f"{username}: ", tag)
        self.chat_display.insert("end", f"{content}\n", "message")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _update_user_list(self, users):
        self.users_listbox.delete(0, tk.END)
        for user in sorted(users):
            display = f"● {user}"
            if user == self.username:
                display += " (tú)"
            self.users_listbox.insert(tk.END, display)

    # ── Envío de mensajes ──────────────────────────────────
    def _send_message(self):
        content = self.msg_entry.get().strip()
        if not content or not self.websocket:
            return

        self.msg_entry.delete(0, tk.END)

        msg = json.dumps({
            "type": "message",
            "content": content
        })

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(msg), self.loop
            )

    # ── Ejecución ──────────────────────────────────────────
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.running = False
        if self.websocket and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.websocket.close(), self.loop
            )
        self.root.destroy()


if __name__ == "__main__":
    client = ChatClient()
    client.run()
