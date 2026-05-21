import asyncio
import threading
import tkinter as tk
from tkinter import ttk

import websockets


PASSWORD = "123"
HOST = "0.0.0.0"
PORT = 5000

clients = {}
dashboard = None


def log_event(message, level="info"):
    print(message)
    if dashboard is not None:
        dashboard.log(message, level)


def refresh_users():
    if dashboard is not None:
        dashboard.update_users(list(clients.values()))


async def send_system(message):
    dead = []
    for client in list(clients):
        try:
            await client.send(f"SYSTEM:{message}")
        except Exception:
            dead.append(client)

    for client in dead:
        clients.pop(client, None)

    refresh_users()


async def handler(ws):
    log_event("[+] New connection")

    try:
        password = await ws.recv()

        if password != PASSWORD:
            log_event("[!] Rejected login: wrong password", "warning")
            await ws.send("AUTH_FAIL")
            await ws.close()
            return

        name = (await ws.recv()).strip()

        if not name:
            log_event("[!] Rejected login: empty display name", "warning")
            await ws.send("NAME_INVALID")
            await ws.close()
            return

        active_names = set(clients.values())
        if name in active_names:
            log_event(f"[!] Rejected login: duplicate name {name}", "warning")
            await ws.send("NAME_TAKEN")
            await ws.close()
            return

        clients[ws] = name
        refresh_users()
        await ws.send("AUTH_OK")

        log_event(f"[+] {name} joined | Clients: {len(clients)}", "success")
        await send_system(f"{name} joined the room.")

        async for message in ws:
            log_event(f"[relay] encrypted message from {name} ({len(message)} chars)")

            dead = []
            for client in list(clients):
                if client is ws:
                    continue
                try:
                    await client.send(message)
                except Exception:
                    dead.append(client)

            for client in dead:
                clients.pop(client, None)

            refresh_users()

    except Exception as e:
        log_event(f"[!] Connection error: {e}", "error")

    finally:
        name = clients.pop(ws, None)
        refresh_users()
        if name:
            log_event(f"[-] {name} left | Clients: {len(clients)}")
            await send_system(f"{name} left the room.")
        else:
            log_event(f"[-] Connection closed before joining | Clients: {len(clients)}")


async def main():
    async with websockets.serve(handler, HOST, PORT):
        log_event(f"[*] Secure chat server running on port {PORT}", "success")
        await asyncio.Future()


def run_server():
    asyncio.run(main())


class ServerDashboard:
    def __init__(self):
        global dashboard
        dashboard = self

        self.window = tk.Tk()
        self.window.title("Secure Chat Server")
        self.window.geometry("760x520")
        self.window.minsize(560, 420)
        self.window.configure(bg="#f4f7fb")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.configure_styles()
        self.build_ui()

        threading.Thread(target=run_server, daemon=True).start()

    def configure_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("App.TFrame", background="#f4f7fb")
        self.style.configure("Header.TFrame", background="#152238")
        self.style.configure(
            "HeaderTitle.TLabel",
            background="#152238",
            foreground="#ffffff",
            font=("Segoe UI", 16, "bold"),
        )
        self.style.configure(
            "HeaderSub.TLabel",
            background="#152238",
            foreground="#b8c7dc",
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Status.TLabel",
            background="#f4f7fb",
            foreground="#536270",
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "PanelTitle.TLabel",
            background="#f4f7fb",
            foreground="#152238",
            font=("Segoe UI", 10, "bold"),
        )

    def build_ui(self):
        header = ttk.Frame(self.window, style="Header.TFrame", padding=(18, 14))
        header.pack(fill="x")

        ttk.Label(header, text="Secure Chat Server", style="HeaderTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            header,
            text="Room coordination dashboard; message contents stay encrypted.",
            style="HeaderSub.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(self.window, style="App.TFrame", padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        self.status_label = ttk.Label(
            body,
            text=f"Listening on {HOST}:{PORT}",
            style="Status.TLabel",
        )
        self.status_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Label(body, text="Active Users", style="PanelTitle.TLabel").grid(
            row=1, column=0, sticky="nw", pady=(0, 6)
        )
        ttk.Label(body, text="Security Events", style="PanelTitle.TLabel").grid(
            row=1, column=1, sticky="nw", padx=(14, 0), pady=(0, 6)
        )

        self.users_box = tk.Listbox(
            body,
            bg="#ffffff",
            fg="#17212b",
            font=("Segoe UI", 10),
            relief="flat",
            highlightthickness=1,
            highlightbackground="#d8e1ec",
            selectbackground="#dbeafe",
            activestyle="none",
        )
        self.users_box.grid(row=2, column=0, sticky="nsew", pady=(24, 0))

        log_frame = ttk.Frame(body, style="App.TFrame")
        log_frame.grid(row=2, column=1, sticky="nsew", padx=(14, 0), pady=(24, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_box = tk.Text(
            log_frame,
            wrap="word",
            state="disabled",
            bg="#ffffff",
            fg="#17212b",
            font=("Consolas", 10),
            relief="flat",
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground="#d8e1ec",
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_box.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_box.configure(yscrollcommand=scrollbar.set)

        self.log_box.tag_configure("info", foreground="#536270")
        self.log_box.tag_configure("success", foreground="#137333")
        self.log_box.tag_configure("warning", foreground="#9a6700")
        self.log_box.tag_configure("error", foreground="#b42318")

    def log(self, message, level="info"):
        self.window.after(0, self._log, message, level)

    def _log(self, message, level):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, f"{message}\n", level)
        self.log_box.configure(state="disabled")
        self.log_box.see(tk.END)

    def update_users(self, names):
        self.window.after(0, self._update_users, names)

    def _update_users(self, names):
        self.users_box.delete(0, tk.END)
        for name in sorted(names):
            self.users_box.insert(tk.END, name)
        self.status_label.configure(
            text=f"Listening on {HOST}:{PORT} | Active users: {len(names)}"
        )

    def close(self):
        self.window.destroy()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    ServerDashboard().run()
