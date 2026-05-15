from __future__ import annotations

import base64
import select
import socket
import socketserver
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse


class _UCBridgeTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_cls, upstream: dict):
        super().__init__(server_address, handler_cls)
        self.upstream = upstream
        self.bridge = None

    def handle_error(self, request, client_address):
        if self.bridge is not None:
            self.bridge._record_error("request_handler_error")


class _UCBridgeHandler(BaseHTTPRequestHandler):
    timeout = 20

    def log_message(self, format, *args):
        return

    @property
    def upstream(self) -> dict:
        return self.server.upstream

    def do_CONNECT(self):
        self.server.bridge._record_request()
        upstream_sock = self._connect_upstream()
        if upstream_sock is None:
            self.send_error(502)
            return
        try:
            request = [f"CONNECT {self.path} HTTP/1.1"]
            if self.upstream.get("auth_header"):
                request.append(f"Proxy-Authorization: {self.upstream['auth_header']}")
            request.append(f"Host: {self.path}")
            request.append("Connection: keep-alive")
            request.append("")
            request.append("")
            upstream_sock.sendall("\r\n".join(request).encode())

            response = self._read_http_headers(upstream_sock)
            if b"200" not in response.split(b"\r\n", 1)[0]:
                self.server.bridge._record_error("upstream_connect_rejected")
                self.wfile.write(response)
                return

            self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self._relay_bidirectional(self.connection, upstream_sock)
        finally:
            try:
                upstream_sock.close()
            except Exception:
                pass

    def do_GET(self):
        self._forward_http_request()

    def do_POST(self):
        self._forward_http_request()

    def do_HEAD(self):
        self._forward_http_request()

    def _forward_http_request(self):
        self.server.bridge._record_request()
        upstream_sock = self._connect_upstream()
        if upstream_sock is None:
            self.send_error(502)
            return
        try:
            body = b""
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                body = self.rfile.read(length)

            request_line = f"{self.command} {self.path} {self.request_version}\r\n"
            upstream_sock.sendall(request_line.encode())
            for key, value in self.headers.items():
                if key.lower() == "proxy-authorization":
                    continue
                upstream_sock.sendall(f"{key}: {value}\r\n".encode())
            if self.upstream.get("auth_header"):
                upstream_sock.sendall(
                    f"Proxy-Authorization: {self.upstream['auth_header']}\r\n".encode()
                )
            upstream_sock.sendall(b"\r\n")
            if body:
                upstream_sock.sendall(body)

            while True:
                chunk = upstream_sock.recv(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        finally:
            try:
                upstream_sock.close()
            except Exception:
                pass

    def _connect_upstream(self):
        try:
            upstream_sock = socket.create_connection(
                (self.upstream["host"], self.upstream["port"]), timeout=self.timeout
            )
            return upstream_sock
        except Exception:
            self.server.bridge._record_error("upstream_connect_failed")
            return None

    @staticmethod
    def _read_http_headers(sock) -> bytes:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data

    @staticmethod
    def _relay_bidirectional(client_sock, upstream_sock) -> None:
        sockets = [client_sock, upstream_sock]
        while True:
            readable, _, errored = select.select(sockets, [], sockets, 5)
            if errored:
                break
            if not readable:
                continue
            for src in readable:
                dst = upstream_sock if src is client_sock else client_sock
                try:
                    data = src.recv(65536)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    return
                if not data:
                    return
                try:
                    dst.sendall(data)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    return


class UCProxyBridge:
    def __init__(self, upstream_proxy_url: str):
        parsed = urlparse(upstream_proxy_url)
        if not parsed.hostname or not parsed.port:
            raise ValueError("Invalid upstream proxy URL")
        self.upstream = {
            "host": parsed.hostname,
            "port": parsed.port,
            "username": parsed.username or "",
            "password": parsed.password or "",
        }
        auth = f"{self.upstream['username']}:{self.upstream['password']}".encode()
        self.upstream["auth_header"] = f"Basic {base64.b64encode(auth).decode()}"
        self._server: _UCBridgeTCPServer | None = None
        self._thread: threading.Thread | None = None
        self.request_count = 0
        self.error_count = 0
        self.last_error = ""

    def start(self) -> None:
        if self._server is not None:
            return
        self._server = _UCBridgeTCPServer(("127.0.0.1", 0), _UCBridgeHandler, self.upstream)
        self._server.bridge = self
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None

    def local_proxy_url(self) -> str:
        if self._server is None:
            raise RuntimeError("Bridge not started")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def healthy(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def _record_request(self) -> None:
        self.request_count += 1

    def _record_error(self, error: str) -> None:
        self.error_count += 1
        self.last_error = error

    def snapshot(self) -> dict:
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "healthy": self.healthy(),
        }
