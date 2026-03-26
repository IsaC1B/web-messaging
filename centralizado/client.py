"""
Cliente de Chat WebSocket (Python / Tkinter)
Soporta: chat general, chat privado, grupos.

CONFIGURACIÓN:
  - Edita SERVER_HOST con la IP del servidor (o "localhost" si es el mismo equipo).
  - Deja SERVER_PORT en 8766 (o cámbialo si tu servidor usa otro puerto).
"""

import asyncio
import websockets
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from datetime import datetime


SERVER_HOST = "192.168.52.53"   # Ejemplo: "192.168.1.100"
SERVER_PORT = 8766


WS_URI = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/chat/"


class ChatClient:
    """Cliente de chat multi-panel con interfaz gráfica tkinter."""

    BG      = "#0f0f23"
    BG2     = "#1a1a35"
    BG_INP  = "#1e1e3a"
    FG      = "#e8e8f0"
    FGD     = "#6b6b8d"
    ACCENT  = "#00f5d4"
    ACCENT2 = "#9b5cff"
    PRIV    = "#f59e0b"
    GROUP   = "#34d399"
    GREEN   = "#2ecc71"
    BLUE    = "#3b82f6"
    RED     = "#ef4444"

    def __init__(self):
        self.websocket   = None
        self.loop        = None
        self.running     = False
        self.username    = None

        # Pestañas: {tab_id: {"label": str, "widget": Text, "frame": Frame, "unread": int}}
        self.tabs        = {}
        self.active_tab  = "general"
        self.tab_buttons = {}

        # Usuarios y grupos conocidos
        self.online_users = []
        self.known_groups = []

        self.root = tk.Tk()
        self.root.title("💬 Chat WebSocket — Cliente Python")
        self.root.geometry("920x640")
        self.root.minsize(700, 500)
        self.root.configure(bg=self.BG)

        self._build_login()


    def _build_login(self):
        self.login_frame = tk.Frame(self.root, bg=self.BG)
        self.login_frame.place(relx=.5, rely=.5, anchor="center")

        tk.Label(self.login_frame, text="💬", font=("Segoe UI Emoji",48),
                 bg=self.BG, fg=self.FG).pack(pady=(0,4))
        tk.Label(self.login_frame, text="Chat WebSocket",
                 font=("Segoe UI",22,"bold"), bg=self.BG, fg=self.FG).pack()
        tk.Label(self.login_frame, text=f"→  {WS_URI}",
                 font=("Segoe UI",10), bg=self.BG, fg=self.FGD).pack(pady=(2,20))

        tk.Label(self.login_frame, text="Nombre de usuario:",
                 font=("Segoe UI",12), bg=self.BG, fg=self.FG).pack()

        self.uentry = tk.Entry(
            self.login_frame, font=("Segoe UI",14), width=26, justify="center",
            bg=self.BG_INP, fg=self.ACCENT, insertbackground=self.FG,
            relief="flat", highlightthickness=2,
            highlightcolor=self.ACCENT, highlightbackground=self.ACCENT2)
        self.uentry.pack(pady=(6,14), ipady=7)
        self.uentry.focus_set()
        self.uentry.bind("<Return>", lambda _: self._connect())

        self.conn_btn = tk.Button(
            self.login_frame, text="Conectarse",
            font=("Segoe UI",13,"bold"),
            bg=self.ACCENT, fg="black", relief="flat", cursor="hand2",
            padx=30, pady=8, command=self._connect)
        self.conn_btn.pack(pady=(0,8))

        self.status_lbl = tk.Label(self.login_frame, text="",
                                   font=("Segoe UI",10), bg=self.BG, fg=self.FGD)
        self.status_lbl.pack()

  
    def _build_chat_ui(self):
        self.login_frame.destroy()

        # ── Header ──────────────────────────────────────────
        header = tk.Frame(self.root, bg="#0f2027", height=48)
        header.pack(fill="x"); header.pack_propagate(False)
        tk.Label(header, text=f"💬 Chat  —  {self.username}",
                 font=("Segoe UI",13,"bold"), bg="#0f2027", fg="white"
                 ).pack(side="left", padx=14, pady=10)
        tk.Label(header, text=f"🔗 {WS_URI}",
                 font=("Segoe UI",9), bg="#0f2027", fg="#aaaacc"
                 ).pack(side="right", padx=14, pady=10)

        # ── Body ─────────────────────────────────────────────
        body = tk.Frame(self.root, bg=self.BG)
        body.pack(fill="both", expand=True)

        # Sidebar
        self._build_sidebar(body)

        # Área de pestañas + mensajes + input
        right = tk.Frame(body, bg=self.BG)
        right.pack(side="left", fill="both", expand=True)

        self._build_tab_bar(right)
        self._build_message_area(right)
        self._build_input_bar(right)

        # Pestaña General
        self._open_tab("general", "🌐 General")

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=self.BG2, width=200)
        sb.pack(side="left", fill="y"); sb.pack_propagate(False)

        # ── Usuarios ──────────────────────────────────────────
        tk.Label(sb, text="👥 USUARIOS", font=("Segoe UI",9,"bold"),
                 bg=self.BG2, fg=self.FGD).pack(pady=(10,4), padx=10, anchor="w")
        sep = tk.Frame(sb, bg=self.ACCENT, height=1); sep.pack(fill="x", padx=10, pady=(0,4))

        self.users_lb = tk.Listbox(
            sb, font=("Segoe UI",11), bg=self.BG2, fg=self.FG,
            relief="flat", bd=0, highlightthickness=0,
            selectbackground=self.ACCENT2, activestyle="none", height=8)
        self.users_lb.pack(fill="x", padx=8, pady=(0,6))
        self.users_lb.bind("<Double-Button-1>", self._on_user_dblclick)

        # ── Grupos ────────────────────────────────────────────
        grp_header = tk.Frame(sb, bg=self.BG2)
        grp_header.pack(fill="x", padx=10, pady=(6,4))
        tk.Label(grp_header, text="🏠 GRUPOS", font=("Segoe UI",9,"bold"),
                 bg=self.BG2, fg=self.FGD).pack(side="left")
        tk.Button(grp_header, text="＋", font=("Segoe UI",12), bg=self.BG2,
                  fg=self.ACCENT, relief="flat", cursor="hand2",
                  command=self._create_group).pack(side="right")

        sep2 = tk.Frame(sb, bg=self.GROUP, height=1); sep2.pack(fill="x", padx=10, pady=(0,4))

        self.groups_lb = tk.Listbox(
            sb, font=("Segoe UI",11), bg=self.BG2, fg=self.FG,
            relief="flat", bd=0, highlightthickness=0,
            selectbackground=self.ACCENT2, activestyle="none")
        self.groups_lb.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.groups_lb.bind("<Double-Button-1>", self._on_group_dblclick)

    def _build_tab_bar(self, parent):
        self.tab_frame = tk.Frame(parent, bg=self.BG2, height=36)
        self.tab_frame.pack(fill="x"); self.tab_frame.pack_propagate(False)

    def _build_message_area(self, parent):
        self.msg_notebook = tk.Frame(parent, bg=self.BG)
        self.msg_notebook.pack(fill="both", expand=True)

    def _build_input_bar(self, parent):
        bar = tk.Frame(parent, bg=self.BG2, height=52)
        bar.pack(fill="x"); bar.pack_propagate(False)

        self.msg_entry = tk.Entry(
            bar, font=("Segoe UI",13), bg=self.BG_INP, fg=self.FG,
            insertbackground=self.FG, relief="flat",
            highlightthickness=2, highlightcolor=self.ACCENT2,
            highlightbackground=self.BG_INP)
        self.msg_entry.pack(side="left", fill="both", expand=True, padx=(10,8), pady=10, ipady=4)
        self.msg_entry.bind("<Return>", lambda _: self._send())
        self.msg_entry.focus_set()

        self.send_btn = tk.Button(
            bar, text="Enviar ➤", font=("Segoe UI",12,"bold"),
            bg=self.ACCENT, fg="black", relief="flat", cursor="hand2",
            padx=16, command=self._send)
        self.send_btn.pack(side="right", padx=(0,10), pady=10)


    def _open_tab(self, tab_id, label, closable=False):
        if tab_id in self.tabs:
            self._switch_tab(tab_id); return

        # Botón de pestaña
        btn_frame = tk.Frame(self.tab_frame, bg=self.BG2)
        btn_frame.pack(side="left", padx=(4,0), pady=4)

        btn = tk.Button(btn_frame, text=label, font=("Segoe UI",10),
                        bg=self.BG2, fg=self.FGD, relief="flat", cursor="hand2",
                        padx=10, pady=3,
                        command=lambda t=tab_id: self._switch_tab(t))
        btn.pack(side="left")

        if closable:
            close = tk.Button(btn_frame, text="×", font=("Segoe UI",11),
                              bg=self.BG2, fg=self.FGD, relief="flat", cursor="hand2",
                              command=lambda t=tab_id: self._close_tab(t))
            close.pack(side="left")

        # Panel de mensajes
        frame = tk.Frame(self.msg_notebook, bg=self.BG)
        txt = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, state="disabled",
            font=("Consolas",11), bg=self.BG2, fg=self.FG,
            relief="flat", bd=0, padx=12, pady=12)
        txt.pack(fill="both", expand=True)

        # Tags
        txt.tag_config("system",   foreground="#f39c12", font=("Consolas",10,"italic"))
        txt.tag_config("username", foreground=self.BLUE, font=("Consolas",11,"bold"))
        txt.tag_config("own_usr",  foreground=self.ACCENT, font=("Consolas",11,"bold"))
        txt.tag_config("priv_usr", foreground=self.PRIV, font=("Consolas",11,"bold"))
        txt.tag_config("grp_usr",  foreground=self.GROUP, font=("Consolas",11,"bold"))
        txt.tag_config("ts",       foreground=self.FGD, font=("Consolas",9))
        txt.tag_config("content",  foreground=self.FG,  font=("Consolas",11))
        txt.tag_config("badge",    foreground=self.PRIV, font=("Consolas",9,"italic"))

        self.tabs[tab_id] = {"label": label, "frame": frame, "txt": txt,
                             "btn": btn, "btn_frame": btn_frame, "unread": 0}
        self.tab_buttons[tab_id] = btn

        self._switch_tab(tab_id)

    def _switch_tab(self, tab_id):
        if tab_id not in self.tabs:
            return
        self.active_tab = tab_id

        # Ocultar todos los paneles
        for tid, t in self.tabs.items():
            t["frame"].pack_forget()
            t["btn"].config(bg=self.BG2, fg=self.FGD)

        # Mostrar el activo
        self.tabs[tab_id]["frame"].pack(fill="both", expand=True)
        self.tabs[tab_id]["btn"].config(bg=self.BG, fg=self.FG)
        self.tabs[tab_id]["unread"] = 0
        self._refresh_tab_label(tab_id)

        # Placeholder del input
        ph = "Escribe un mensaje..."
        if tab_id.startswith("priv_"):
            ph = f"Mensaje privado a {tab_id[5:]}..."
        elif tab_id.startswith("group_"):
            ph = f"Mensaje al grupo {tab_id[6:]}..."
        self.msg_entry.config(fg=self.FGD if not self.msg_entry.get() else self.FG)
        # (solo actualizar placeholder visual si quieres, tkinter no tiene placeholder nativo)

        self.msg_entry.focus_set()

    def _close_tab(self, tab_id):
        if tab_id == "general":
            return
        if tab_id.startswith("group_"):
            gname = tab_id[6:]
            self._ws_send({"type": "leave_group", "group_name": gname})

        t = self.tabs.pop(tab_id, None)
        if t:
            t["frame"].destroy()
            t["btn_frame"].destroy()

        if self.active_tab == tab_id:
            self._switch_tab("general")

    def _refresh_tab_label(self, tab_id):
        t = self.tabs.get(tab_id)
        if not t:
            return
        label = t["label"]
        if t["unread"] > 0:
            label += f"  [{t['unread']}]"
        t["btn"].config(text=label)

    def _bump_unread(self, tab_id):
        if self.active_tab == tab_id:
            return
        t = self.tabs.get(tab_id)
        if t:
            t["unread"] += 1
            self._refresh_tab_label(tab_id)

    def _append(self, tab_id, parts):
        """parts = list of (text, tag)"""
        t = self.tabs.get(tab_id)
        if not t:
            return
        txt = t["txt"]
        txt.config(state="normal")
        for text, tag in parts:
            txt.insert("end", text, tag)
        txt.config(state="disabled")
        txt.see("end")
        self._bump_unread(tab_id)

    def _sys(self, tab_id, content, ts=""):
        parts = []
        if ts:
            parts.append((f"[{ts}] ", "ts"))
        parts.append((content + "\n", "system"))
        self._append(tab_id, parts)

    def _chat(self, tab_id, username, content, ts, is_own, mode="general"):
        usr_tag = "own_usr" if is_own else ("priv_usr" if mode == "priv" else ("grp_usr" if mode == "group" else "username"))
        parts = []
        if ts:
            parts.append((f"[{ts}] ", "ts"))
        parts.append((f"{username}: ", usr_tag))
        if mode == "priv":
            parts.append(("[privado] ", "badge"))
        parts.append((content + "\n", "content"))
        self._append(tab_id, parts)

    def _on_message(self, data):
        t = data.get("type")

        if t == "system":
            gname = data.get("group_name")
            tid = ("group_" + gname) if gname and ("group_" + gname) in self.tabs else "general"
            self._sys(tid, data.get("content", ""), data.get("timestamp", ""))

        elif t == "message":
            ctx = data.get("chat_context", "general")
            gname = data.get("group_name")
            if ctx == "group" and gname:
                tid = "group_" + gname
                if tid not in self.tabs:
                    return
                self._chat(tid, data["username"], data["content"],
                           data.get("timestamp",""), data.get("is_own",False), "group")
            else:
                self._chat("general", data["username"], data["content"],
                           data.get("timestamp",""), data.get("is_own",False))

        elif t == "private_msg":
            partner = data["target"] if data.get("is_own") else data["sender"]
            tid = "priv_" + partner
            if tid not in self.tabs:
                label = f"🔒 {partner}"
                self.root.after(0, lambda l=label, ti=tid: self._open_tab(ti, l, closable=True))
            direction = f"→ {data['target']}" if data.get("is_own") else f"← {data['sender']}"
            self._chat(tid, direction, data["content"],
                       data.get("timestamp",""), data.get("is_own",False), "priv")

        elif t == "user_list":
            self.online_users = data.get("users", [])
            self.root.after(0, self._render_users)

        elif t == "group_list":
            self.known_groups = data.get("groups", [])
            self.root.after(0, self._render_groups)

        elif t == "group_joined":
            gname = data["group_name"]
            tid = "group_" + gname
            label = f"🏠 {gname}"
            self.root.after(0, lambda l=label, ti=tid: self._open_tab(ti, l, closable=True))
            self._sys(tid, f"Te uniste al grupo «{gname}»", data.get("timestamp",""))

        elif t == "group_left":
            gname = data.get("group_name","")
            tid = "group_" + gname
            self.root.after(0, lambda ti=tid: self._close_tab(ti))

        elif t == "error":
            self.root.after(0, lambda m=data.get("content",""): messagebox.showerror("Error", m, parent=self.root))

    def _render_users(self):
        self.users_lb.delete(0, tk.END)
        for u in sorted(self.online_users):
            tag = f"● {u}" + (" (tú)" if u == self.username else "")
            self.users_lb.insert(tk.END, tag)

    def _render_groups(self):
        self.groups_lb.delete(0, tk.END)
        for g in self.known_groups:
            self.groups_lb.insert(tk.END, f"🏠 {g['name']}  [{g['count']}]")


    def _on_user_dblclick(self, event):
        sel = self.users_lb.curselection()
        if not sel:
            return
        raw = self.users_lb.get(sel[0])
        # "● username (tú)" → extraer nombre
        name = raw.lstrip("● ").split(" (tú)")[0].strip()
        if name == self.username:
            return
        tid = "priv_" + name
        if tid not in self.tabs:
            self._open_tab(tid, f"🔒 {name}", closable=True)
        else:
            self._switch_tab(tid)

    def _on_group_dblclick(self, event):
        sel = self.groups_lb.curselection()
        if not sel:
            return
        raw = self.groups_lb.get(sel[0])
        gname = raw.lstrip("🏠 ").split("  [")[0].strip()
        tid = "group_" + gname
        if tid in self.tabs:
            self._switch_tab(tid)
        else:
            self._ws_send({"type": "join_group", "group_name": gname})

    def _create_group(self):
        name = simpledialog.askstring("Crear grupo", "Nombre del grupo:",
                                      parent=self.root)
        if name and name.strip():
            self._ws_send({"type": "create_group", "group_name": name.strip()})

    def _send(self):
        content = self.msg_entry.get().strip()
        if not content:
            return
        self.msg_entry.delete(0, tk.END)

        if self.active_tab == "general":
            self._ws_send({"type": "message", "content": content})
        elif self.active_tab.startswith("priv_"):
            target = self.active_tab[5:]
            self._ws_send({"type": "private_message", "target": target, "content": content})
        elif self.active_tab.startswith("group_"):
            gname = self.active_tab[6:]
            self._ws_send({"type": "group_message", "group_name": gname, "content": content})

    def _ws_send(self, obj):
        msg = json.dumps(obj)
        if self.loop and self.loop.is_running() and self.websocket:
            asyncio.run_coroutine_threadsafe(self.websocket.send(msg), self.loop)


    def _connect(self):
        self.username = self.uentry.get().strip()
        if not self.username:
            self.status_lbl.config(text="Ingresa un nombre", fg=self.RED)
            return
        self.status_lbl.config(text="Conectando...", fg=self.FGD)
        self.conn_btn.config(state="disabled")
        self.running = True
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._ws_handler())
        except Exception as e:
            self.root.after(0, lambda m=str(e): self._conn_error(m))

    async def _ws_handler(self):
        try:
            async with websockets.connect(WS_URI) as ws:
                self.websocket = ws
                await ws.send(json.dumps({"type": "join", "username": self.username}))
                self.root.after(0, self._build_chat_ui)
                async for raw in ws:
                    data = json.loads(raw)
                    self.root.after(0, lambda d=data: self._on_message(d))
        except (ConnectionRefusedError, OSError):
            raise Exception(f"No se pudo conectar a {WS_URI}")
        except websockets.ConnectionClosed:
            self.root.after(0, lambda: self._sys("general", "⚠️ Conexión perdida"))
        finally:
            self.running = False

    def _conn_error(self, msg):
        self.status_lbl.config(text=f" {msg}", fg=self.RED)
        self.conn_btn.config(state="normal")

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.running = False
        if self.websocket and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
        self.root.destroy()

if __name__ == "__main__":
    ChatClient().run()
