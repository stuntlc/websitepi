"""Use a single listening socket supplied by systemd."""
import http.server
import os
import socket


def activated_server(handler, port, server_class=http.server.ThreadingHTTPServer):
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise RuntimeError("Expected one systemd-activated listening socket")
    listener = socket.socket(fileno=3)
    if (listener.family != socket.AF_INET or listener.type != socket.SOCK_STREAM or
            not listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) or
            listener.getsockname()[1] != port):
        listener.close()
        raise RuntimeError("Invalid systemd-activated listening socket")
    server = server_class(("", port), handler, bind_and_activate=False)
    server.socket.close()
    server.socket = listener
    server.server_address = listener.getsockname()
    server.server_name = socket.getfqdn()
    server.server_port = port
    return server
