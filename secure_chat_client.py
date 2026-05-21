import asyncio
import base64
import hashlib
import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import websockets
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class ChatClient:
    def __init__(self):
        self.url = ""
        self.name = ""
        self.password = ""
        self.KEY = None

        self.ws = None
        self.connected = False
        self.private_key = None
        self.public_key_text = ""
        self.known_peers = {}

        self.window = tk.Tk()
        self.window.title("Secure Chat")
        self.window.geometry("760x560")
        self.window.minsize(520, 420)
        self.window.configure(bg="#f4f7fb")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_loop, daemon=True).start()

        self.configure_styles()
        self.build_login_ui()

    @property
    def app_dir(self):
        safe_name = "".join(c for c in self.name if c.isalnum() or c in ("-", "_"))
        if not safe_name:
            safe_name = "anonymous"
        return Path.home() / ".secure_chat" / safe_name

    @property
    def private_key_path(self):
        return self.app_dir / "identity_private.pem"

    @property
    def known_peers_path(self):
        return self.app_dir / "known_peers.json"

    def configure_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("App.TFrame", background="#f4f7fb")
        self.style.configure("Card.TFrame", background="#ffffff")
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
            "Title.TLabel",
            background="#f4f7fb",
            foreground="#152238",
            font=("Segoe UI", 18, "bold"),
        )
        self.style.configure(
            "Field.TLabel",
            background="#ffffff",
            foreground="#536270",
            font=("Segoe UI", 9, "bold"),
        )
        self.style.configure(
            "Hint.TLabel",
            background="#f4f7fb",
            foreground="#697789",
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Status.TLabel",
            background="#f4f7fb",
            foreground="#536270",
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Send.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(18, 8),
            background="#276ef1",
            foreground="#ffffff",
        )
        self.style.configure(
            "Connect.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(16, 9),
            background="#276ef1",
            foreground="#ffffff",
        )
        self.style.map(
            "Send.TButton",
            background=[("active", "#1d5fd2"), ("disabled", "#98a8bc")],
            foreground=[("disabled", "#edf2f7")],
        )
        self.style.map(
            "Connect.TButton",
            background=[("active", "#1d5fd2"), ("disabled", "#98a8bc")],
            foreground=[("disabled", "#edf2f7")],
        )

    def build_login_ui(self):
        self.clear_window()

        self.login_frame = ttk.Frame(self.window, style="App.TFrame", padding=24)
        self.login_frame.pack(fill="both", expand=True)
        self.login_frame.columnconfigure(0, weight=1)

        ttk.Label(
            self.login_frame,
            text="Secure Chat",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.login_frame,
            text="Connect to an encrypted, signed group chat room.",
            style="Hint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 24))

        card = ttk.Frame(self.login_frame, style="Card.TFrame", padding=18)
        card.grid(row=2, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)

        self.url_var = tk.StringVar(value="ws://localhost:5000")
        self.name_var = tk.StringVar()
        self.password_var = tk.StringVar()

        self.add_login_field(card, "Server URL", self.url_var, 0)
        self.add_login_field(card, "Display name", self.name_var, 2)
        self.add_login_field(card, "Shared password", self.password_var, 4, show="*")

        self.login_status = ttk.Label(card, text="", style="Field.TLabel")
        self.login_status.grid(row=6, column=0, sticky="w", pady=(6, 0))

        self.connect_button = ttk.Button(
            card,
            text="Connect",
            style="Connect.TButton",
            command=self.connect_from_login,
        )
        self.connect_button.grid(row=7, column=0, sticky="ew", pady=(14, 0))

        ttk.Label(
            self.login_frame,
            text="Keys are managed locally; users only enter room details.",
            style="Hint.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(14, 0))

        self.window.bind("<Return>", self.connect_from_login)

    def add_login_field(self, parent, label, variable, row, show=None):
        ttk.Label(parent, text=label, style="Field.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        entry = ttk.Entry(parent, textvariable=variable, font=("Segoe UI", 11), show=show)
        entry.grid(row=row + 1, column=0, sticky="ew", ipady=6, pady=(0, 12))
        if row == 0:
            entry.focus_set()
        return entry

    def connect_from_login(self, event=None):
        url = self.url_var.get().strip()
        name = self.name_var.get().strip()
        password = self.password_var.get().strip()

        if not url or not name or not password:
            self.login_status.configure(
                text="Enter a server URL, display name, and password.",
                foreground="#b42318",
            )
            return

        if url.startswith("https://"):
            url = url.replace("https://", "wss://", 1)

        self.url = url
        self.name = name
        self.password = password
        self.KEY = hashlib.sha256(self.password.encode()).digest()
        self.private_key, self.public_key_text = self.load_or_create_identity_key()
        self.known_peers = self.load_known_peers()

        self.window.title(f"Secure Chat - {self.name}")
        self.connect_button.configure(state="disabled")
        self.login_status.configure(text="Connecting...", foreground="#536270")
        asyncio.run_coroutine_threadsafe(self.connect(), self.loop)

    def load_or_create_identity_key(self):
        self.app_dir.mkdir(parents=True, exist_ok=True)

        if self.private_key_path.exists():
            private_key = serialization.load_pem_private_key(
                self.private_key_path.read_bytes(),
                password=None,
            )
        else:
            private_key = Ed25519PrivateKey.generate()
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            self.private_key_path.write_bytes(pem)

        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return private_key, base64.b64encode(public_key).decode()

    def load_known_peers(self):
        if not self.known_peers_path.exists():
            return {}

        try:
            return json.loads(self.known_peers_path.read_text())
        except Exception:
            return {}

    def save_known_peers(self):
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.known_peers_path.write_text(json.dumps(self.known_peers, indent=2))

    def build_chat_ui(self):
        self.clear_window()
        self.window.bind("<Return>", self.send)

        header = ttk.Frame(self.window, style="Header.TFrame", padding=(18, 14))
        header.pack(fill="x")

        ttk.Label(header, text="Secure Chat", style="HeaderTitle.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            header,
            text=f"Encrypted group chat as {self.name}",
            style="HeaderSub.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(self.window, style="App.TFrame", padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        transcript_frame = ttk.Frame(body, style="App.TFrame")
        transcript_frame.grid(row=0, column=0, sticky="nsew")
        transcript_frame.columnconfigure(0, weight=1)
        transcript_frame.rowconfigure(0, weight=1)

        self.chat_box = tk.Text(
            transcript_frame,
            wrap="word",
            state="disabled",
            relief="flat",
            bg="#ffffff",
            fg="#17212b",
            insertbackground="#17212b",
            font=("Segoe UI", 11),
            padx=14,
            pady=14,
            spacing1=4,
            spacing3=8,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#d8e1ec",
            highlightcolor="#8fb3ff",
        )
        self.chat_box.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            transcript_frame, orient="vertical", command=self.chat_box.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.chat_box.configure(yscrollcommand=scrollbar.set)

        self.chat_box.tag_configure(
            "system", foreground="#8a98a8", font=("Segoe UI", 8, "italic")
        )
        self.chat_box.tag_configure(
            "error", foreground="#b42318", font=("Segoe UI", 10, "bold")
        )
        self.chat_box.tag_configure(
            "you", foreground="#0f5fc4", font=("Segoe UI", 11, "bold")
        )
        self.chat_box.tag_configure(
            "peer", foreground="#137333", font=("Segoe UI", 11, "bold")
        )
        self.chat_box.tag_configure("message", foreground="#17212b")

        input_frame = ttk.Frame(body, style="App.TFrame")
        input_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        input_frame.columnconfigure(0, weight=1)

        self.entry = ttk.Entry(input_frame, font=("Segoe UI", 11))
        self.entry.grid(row=0, column=0, sticky="ew", ipady=7)
        self.entry.bind("<Return>", self.send)

        self.send_button = ttk.Button(
            input_frame, text="Send", style="Send.TButton", command=self.send
        )
        self.send_button.grid(row=0, column=1, padx=(10, 0))

        footer = ttk.Frame(body, style="App.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(
            footer, text="Connected | Encrypted | Signed", style="Status.TLabel"
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        self.url_label = ttk.Label(
            footer, text=self.relay_label(), style="Status.TLabel"
        )
        self.url_label.grid(row=0, column=1, sticky="e")

        self.set_input_enabled(True)
        self.add_line("Connected securely.", "system")

    def relay_label(self):
        if "ngrok" in self.url:
            return "Relay: ngrok"
        if "loca.lt" in self.url:
            return "Relay: localtunnel"
        if "localhost" in self.url or "127.0.0.1" in self.url:
            return "Relay: local"
        return "Relay connected"

    def clear_window(self):
        for child in self.window.winfo_children():
            child.destroy()

    def encrypt(self, msg):
        aesgcm = AESGCM(self.KEY)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, msg.encode(), None)
        return (nonce + ct).hex()

    def decrypt(self, data):
        aesgcm = AESGCM(self.KEY)
        raw = bytes.fromhex(data)
        nonce = raw[:12]
        ct = raw[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()

    def sign_message(self, sender, text):
        signed_data = self.message_to_sign(sender, text)
        signature = self.private_key.sign(signed_data)
        return base64.b64encode(signature).decode()

    def verify_signature(self, sender, text, public_key_text, signature_text):
        public_key_bytes = base64.b64decode(public_key_text)
        signature = base64.b64decode(signature_text)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature, self.message_to_sign(sender, text))

    def message_to_sign(self, sender, text):
        return json.dumps(
            {"sender": sender, "text": text},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    def make_encrypted_payload(self, text):
        payload = {
            "sender": self.name,
            "text": text,
            "public_key": self.public_key_text,
            "signature": self.sign_message(self.name, text),
        }
        return self.encrypt(json.dumps(payload, separators=(",", ":")))

    def read_encrypted_payload(self, encrypted_message):
        payload = json.loads(self.decrypt(encrypted_message))
        required = ("sender", "text", "public_key", "signature")
        if not all(field in payload for field in required):
            raise ValueError("missing message fields")

        self.verify_signature(
            payload["sender"],
            payload["text"],
            payload["public_key"],
            payload["signature"],
        )
        self.check_peer_identity(payload["sender"], payload["public_key"])
        return payload["sender"], payload["text"]

    def check_peer_identity(self, sender, public_key_text):
        if sender == self.name:
            return

        known_key = self.known_peers.get(sender)
        if known_key is None:
            self.known_peers[sender] = public_key_text
            self.save_known_peers()
            self.ui(self.add_line, f"New peer trusted: {sender}", "system")
            return

        if known_key != public_key_text:
            raise ValueError(f"{sender}'s identity key changed")

    def start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def connect(self):
        try:
            self.ws = await websockets.connect(self.url)
            await self.ws.send(self.password)
            await self.ws.send(self.name)

            response = await self.ws.recv()
            if response == "AUTH_FAIL":
                self.ui(self.show_login_error, "Wrong password.")
                return
            if response == "NAME_TAKEN":
                self.ui(self.show_login_error, "Choose another display name.")
                return
            if response == "NAME_INVALID":
                self.ui(self.show_login_error, "Display name cannot be empty.")
                return
            if response != "AUTH_OK":
                self.ui(self.show_login_error, f"Unexpected server response: {response}")
                return

            self.connected = True
            self.ui(self.build_chat_ui)

            async for msg in self.ws:
                if msg.startswith("SYSTEM:"):
                    self.ui(self.add_line, msg.replace("SYSTEM:", "", 1), "system")
                    continue

                try:
                    sender, text = self.read_encrypted_payload(msg)
                    self.ui(self.add_message, sender, text, "peer")
                except InvalidSignature:
                    self.ui(self.add_line, "Blocked message with invalid signature.", "error")
                except Exception as e:
                    self.ui(self.add_line, f"Blocked message: {e}", "error")

        except websockets.ConnectionClosedOK:
            self.connected = False
            self.ui(self.show_disconnected)
        except Exception as e:
            self.connected = False
            self.ui(self.show_login_or_chat_error, f"Connection error: {e}")

    def show_login_error(self, message):
        self.connected = False
        self.connect_button.configure(state="normal")
        self.login_status.configure(text=message, foreground="#b42318")

    def show_disconnected(self):
        if hasattr(self, "chat_box") and self.chat_box.winfo_exists():
            self.set_status("Disconnected", False)
            self.add_line("Connection closed by the server.", "system")
        else:
            self.show_login_error("Connection closed by the server.")

    def show_login_or_chat_error(self, message):
        if hasattr(self, "chat_box") and self.chat_box.winfo_exists():
            self.set_status("Connection error", False)
            self.add_line(message, "error")
        else:
            self.show_login_error(message)

    def send(self, event=None):
        msg = self.entry.get().strip()
        if not msg or not self.connected or self.ws is None:
            return

        encrypted = self.make_encrypted_payload(msg)
        future = asyncio.run_coroutine_threadsafe(self.ws.send(encrypted), self.loop)
        future.add_done_callback(self.handle_send_result)

        self.add_message("You", msg, "you")
        self.entry.delete(0, tk.END)

    def handle_send_result(self, future):
        try:
            future.result()
        except Exception as e:
            self.connected = False
            self.ui(self.set_status, "Send failed", False)
            self.ui(self.add_line, f"Send failed: {e}", "error")

    def add_message(self, sender, message, sender_tag):
        self.write_to_chat(f"{sender}: ", sender_tag, message)

    def add_line(self, text, tag="message"):
        self.write_to_chat("", tag, text)

    def write_to_chat(self, prefix, prefix_tag, text):
        self.chat_box.configure(state="normal")
        if prefix:
            self.chat_box.insert(tk.END, prefix, prefix_tag)
            self.chat_box.insert(tk.END, f"{text}\n", "message")
        else:
            self.chat_box.insert(tk.END, f"{text}\n", prefix_tag)
        self.chat_box.configure(state="disabled")
        self.chat_box.see(tk.END)

    def set_status(self, text, enabled):
        self.status_label.configure(text=text)
        self.set_input_enabled(enabled)

    def set_input_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.entry.configure(state=state)
        self.send_button.configure(state=state)
        if enabled:
            self.entry.focus_set()

    def ui(self, callback, *args):
        self.window.after(0, callback, *args)

    def close(self):
        self.connected = False
        if self.ws is not None:
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.window.destroy()

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    ChatClient().run()
