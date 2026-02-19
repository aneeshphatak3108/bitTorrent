import socket
import os
class PeerClient:
    def __init__(self, ip, port, info_hash):
        self.ip = ip
        self.port = port
        self.info_hash = bytes.fromhex(info_hash)
        self.peer_id = self.generate_peer_id()

    def generate_peer_id(self):
        return b'-PC0001-' + os.urandom(12)

    def build_handshake(self):
        pstr = b'BitTorrent protocol'
        return (
            bytes([len(pstr)]) +
            pstr +
            b'\x00' * 8 +
            self.info_hash +
            self.peer_id
        )

    def connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((self.ip, self.port))

        handshake = self.build_handshake()
        sock.sendall(handshake)

        response = sock.recv(68)

        if len(response) < 68:
            print("Invalid handshake response")
            return None

        print("Handshake successful with", self.ip, self.port)
        return sock
