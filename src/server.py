import socket
import threading
import json
import argparse
import uuid
import time


class ClientConnection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.id = str(uuid.uuid4())[:8]
        self.name = "Unknown"
        self.buffer = b""
        self.lock = threading.Lock()
        self.alive = True

    def send(self, msg: dict):
        if not self.alive:
            return
        try:
            data = (json.dumps(msg) + "\n").encode("utf-8")
            with self.lock:
                self.sock.sendall(data)
        except OSError:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass


class GameServer:
    """
    Simple TCP JSON-line server.

    - Authoritative state held in self.state (tokens, tilemap, background, meta).
    - Clients send:
        { "type": "join", "client_id": "...", "name": "Player", "protocol_version": 1 }
        { "type": "token_update", "token": { ... token dict ... } }
        { "type": "chat", "from": "Player", "message": "..." }
        { "type": "ping" }
    - Server broadcasts:
        { "type": "state", "protocol_version": 1, "tokens": [...], "tilemap": ..., "background": ..., "campaign_meta": {...} }
        { "type": "token_update", "token": { ... } }
        { "type": "chat", "from": "Player", "message": "..." }
        { "type": "pong" }
        { "type": "error", "message": "..." }
    """

    PROTOCOL_VERSION = 1

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None
        self.clients = []
        self.clients_lock = threading.Lock()
        self.state_lock = threading.Lock()
        # authoritative game state
        self.state = {
            "protocol_version": self.PROTOCOL_VERSION,
            "campaign_meta": {},
            "tokens": [],
            "tilemap": None,
            "background": None,
        }

    # ------------------------------------------------------------------ #
    # Networking
    # ------------------------------------------------------------------ #

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        print(f"[INFO] Listening on {self.host}:{self.port}")

        try:
            while True:
                client_sock, addr = self.sock.accept()
                client = ClientConnection(client_sock, addr)
                with self.clients_lock:
                    self.clients.append(client)
                print(f"[INFO] Client connected from {addr}")
                t = threading.Thread(target=self._client_thread, args=(client,), daemon=True)
                t.start()
        except KeyboardInterrupt:
            print("[INFO] Shutting down server...")
        finally:
            self._shutdown()

    def _shutdown(self):
        with self.clients_lock:
            for c in self.clients:
                c.close()
            self.clients.clear()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _client_thread(self, client: ClientConnection):
        sock = client.sock
        while client.alive:
            try:
                data = sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            client.buffer += data
            while b"\n" in client.buffer:
                line, client.buffer = client.buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    client.send({"type": "error", "message": "Invalid JSON"})
                    continue
                self._handle_message(client, msg)
        print(f"[INFO] Client disconnected: {client.addr}")
        client.close()
        with self.clients_lock:
            if client in self.clients:
                self.clients.remove(client)

    # ------------------------------------------------------------------ #
    # Message Handling
    # ------------------------------------------------------------------ #

    def _handle_message(self, client: ClientConnection, msg: dict):
        mtype = msg.get("type")
        if mtype == "join":
            self._handle_join(client, msg)
        elif mtype == "token_update":
            self._handle_token_update(client, msg)
        elif mtype == "chat":
            self._handle_chat(client, msg)
        elif mtype == "ping":
            client.send({"type": "pong", "time": time.time()})
        elif mtype == "state_update":
            self._handle_state_update(client, msg)
        else:
            client.send({"type": "error", "message": f"Unknown message type: {mtype}"})

    def _handle_join(self, client: ClientConnection, msg: dict):
        proto = msg.get("protocol_version", 0)
        if proto != self.PROTOCOL_VERSION:
            client.send(
                {
                    "type": "error",
                    "message": f"Protocol mismatch (client {proto}, server {self.PROTOCOL_VERSION})",
                }
            )
            client.close()
            return

        client_id = msg.get("client_id") or client.id
        client_name = msg.get("name") or "Player"
        client.id = str(client_id)
        client.name = str(client_name)
        print(f"[INFO] Client joined: {client.name} ({client.id})")

        # send full state snapshot
        with self.state_lock:
            snapshot = {
                "type": "state",
                "protocol_version": self.PROTOCOL_VERSION,
                "campaign_meta": self.state.get("campaign_meta", {}),
                "tokens": self.state.get("tokens", []),
                "tilemap": self.state.get("tilemap"),
                "background": self.state.get("background"),
            }
        client.send(snapshot)

        # optional: broadcast join chat
        join_msg = {
            "type": "chat",
            "from": "SERVER",
            "message": f"{client.name} joined.",
        }
        self._broadcast(join_msg)

    def _handle_token_update(self, client: ClientConnection, msg: dict):
        token = msg.get("token")
        if not isinstance(token, dict):
            client.send({"type": "error", "message": "token_update missing token dict"})
            return

        tid = token.get("id")
        if not tid:
            client.send({"type": "error", "message": "token_update missing token.id"})
            return

        with self.state_lock:
            tokens = self.state.setdefault("tokens", [])
            found = False
            for i, t in enumerate(tokens):
                if t.get("id") == tid:
                    tokens[i] = token
                    found = True
                    break
            if not found:
                tokens.append(token)

        out = {"type": "token_update", "token": token}
        self._broadcast(out)

    def _handle_chat(self, client: ClientConnection, msg: dict):
        text = msg.get("message", "")
        if not isinstance(text, str):
            return
        sender = msg.get("from") or client.name
        out = {
            "type": "chat",
            "from": str(sender),
            "message": text,
        }
        self._broadcast(out)

    def _handle_state_update(self, client: ClientConnection, msg: dict):
        """
        Optional: host can push full state:

        { "type": "state_update", "state": { "tokens": [...], "tilemap": {...}, "background": {...}, "campaign_meta": {...} } }
        """
        st = msg.get("state")
        if not isinstance(st, dict):
            client.send({"type": "error", "message": "state_update missing 'state' dict"})
            return
        with self.state_lock:
            self.state["campaign_meta"] = st.get("campaign_meta", {})
            self.state["tokens"] = st.get("tokens", [])
            self.state["tilemap"] = st.get("tilemap")
            self.state["background"] = st.get("background")

        out = {
            "type": "state",
            "protocol_version": self.PROTOCOL_VERSION,
            "campaign_meta": self.state["campaign_meta"],
            "tokens": self.state["tokens"],
            "tilemap": self.state["tilemap"],
            "background": self.state["background"],
        }
        self._broadcast(out)

    def _broadcast(self, msg: dict):
        with self.clients_lock:
            for c in list(self.clients):
                if not c.alive:
                    continue
                c.send(msg)


def main():
    parser = argparse.ArgumentParser(description="UMI.DA Tabletop LAN Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default 8765)")
    args = parser.parse_args()

    server = GameServer(args.host, args.port)
    server.start()


if __name__ == "__main__":
    main()
