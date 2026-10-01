import os
import socket
import struct


def _query(name: str, ident: int) -> bytes:
    header = struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0)
    labels = b"".join(bytes([len(part)]) + part.encode() for part in name.strip(".").split("."))
    return header + labels + b"\x00" + struct.pack(">HH", 1, 1)


def dns_answers(server: str, name: str = "pi.hole", *, port: int = 53, timeout: float = 3.0, attempts: int = 2) -> bool:
    """True when the DNS server replies to a query for `name` (any reply code counts: the engine is alive)."""
    for _ in range(attempts):
        ident = int.from_bytes(os.urandom(2), "big")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            try:
                sock.sendto(_query(name, ident), (server, port))
                reply, _ = sock.recvfrom(512)
            except OSError:
                continue
        if len(reply) >= 4 and int.from_bytes(reply[:2], "big") == ident and reply[2] & 0x80:
            return True
    return False
