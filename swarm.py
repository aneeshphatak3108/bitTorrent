import socket
import threading
import struct
import random
from core import PeerConnection

class SwarmManager:
    def __init__(self, node):
        self.node = node
        self.peers = node.peers
        self.storage = node.storage
        self.info_hash = node.active_info_hash


    #just outputs the piece number which should be requested
    def choose_piece(self):
        threshold = 0.2 #strategy switching point
        ratio = self.piece_completion_ratio()
        total_pieces = len(self.storage.my_bitfield)

        needed_pieces = [
            i for i in range(total_pieces)
            if self.storage.my_bitfield[i] == 0
        ]
        if not needed_pieces: #we dont need any piece, we are done
            return None

        # RANDOM FIRST STRATEGY
        if ratio < threshold:
            return random.choice(needed_pieces)

        # RAREST FIRST STRATEGY
        piece_count = {p: 0 for p in needed_pieces}
        for peer in self.peers.values():
            if peer.peer_bitfield is None:
                continue
            for p in needed_pieces:
                if peer.peer_bitfield[p] == 1:
                    piece_count[p] += 1
        rarest_piece = min(piece_count, key=piece_count.get)
        return rarest_piece


    #in early game we will be asking for random pieces, and after a point(thats why this function exists ) we do rarest first
    def piece_completion_ratio(self):
        total = len(self.storage.my_bitfield)
        have = sum(self.storage.my_bitfield)
        return have/total

    #seperation of concerns between the dht manager stuff and swarm manager stuff
    def update_peers(self):
        discovered = self.node.iterative_get_peers(self.info_hash)
        for ip, port in discovered:
            if (ip, port) not in self.peers:
                self.peers[(ip, port)] = PeerConnection(ip, port)


    def connect_to_peers(self):
        for peer in self.peers.values(): #key is the (ip, portno.) and value is the PeerConnection object
            if peer.socket is not None:
                continue
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((peer.ip, peer.port))
                peer.socket = sock
                threading.Thread(
                    target=self.handle_peer, #for each peer theres a background worker
                    args=(peer,),
                    daemon=True
                ).start()
            except:
                continue

    #GOAT FUNCTION, DOES A LOT OF THINGS
    def handle_peer(self, peer):
        try:
            #ths is like a pipeline of functions
            self.perform_handshake(peer)
            self.exchange_bitfield(peer)
            self.evaluate_interest(peer)
            while True:
                msg = self.receive_message(peer)
                if msg is None:
                    break
                self.process_message(peer, msg)
        except Exception as e:
            print("Peer error:", e)


    def perform_handshake(self, peer):
        pstr = b"BitTorrent protocol"
        handshake = (
            struct.pack("B", len(pstr))
            + pstr
            + b"\x00" * 8
            + self.info_hash.to_bytes(20, "big")
            + self.node.node_id.to_bytes(20, "big")
        )
        peer.socket.sendall(handshake)
        response = peer.socket.recv(68)
        if len(response) != 68:
            raise Exception("Invalid handshake")


    def send_bitfield(self, peer):
        bitfield = bytes(self.storage.my_bitfield)
        msg = struct.pack(">IB", len(bitfield) + 1, 5) + bitfield
        peer.socket.sendall(msg)
        length = struct.unpack(">I", peer.socket.recv(4))[0]
        msg_id = peer.socket.recv(1)
        if msg_id == b"\x05":
            peer.peer_bitfield = list(peer.socket.recv(length - 1))


    def evaluate_interest(self, peer):
        for i in range(len(self.storage.my_bitfield)):
            if peer.peer_bitfield[i] == 1 and self.storage.my_bitfield[i] == 0:
                self.send_interested(peer)
                peer.am_interested = True
                return
        self.send_not_interested(peer)


    def send_interested(self, peer):
        peer.socket.sendall(struct.pack(">IB", 1, 2))


    def send_not_interested(self, peer):
        peer.socket.sendall(struct.pack(">IB", 1, 3))


    def receive_message(self, peer):
        try:
            length_bytes = peer.socket.recv(4)
            if not length_bytes:
                return None
            length = struct.unpack(">I", length_bytes)[0]
            if length == 0: #this means this is just a keep-alive message to not make tcp connecn idle
                return None
            msg_id = peer.socket.recv(1)
            payload = peer.socket.recv(length - 1)
            return msg_id, payload
        except:
            return None

    '''
    0  CHOKE
    1  UNCHOKE
    2  INTERESTED
    3  NOT_INTERESTED
    4  HAVE
    5  BITFIELD
    6  REQUEST
    7  PIECE
    '''

    def process_message(self, peer, msg):
        msg_id, payload = msg
        if msg_id == b"\x00":
            peer.peer_choking = True

        elif msg_id == b"\x01":
            peer.peer_choking = False #NOTATION ALERT? peer_choking means i am being unchoked so now
            self.request_piece(peer) #use the suvarna sandhi and request a piece

        elif msg_id == b"\x04":  # this was a HAVE msg
            piece = struct.unpack(">I", payload)[0]
            peer.peer_bitfield[piece] = 1

        elif msg_id == b"\x07":  # YOU JUST GOT A PIECE
            piece = struct.unpack(">I", payload[:4])[0]
            block = payload[8:]
            print("Received piece", piece)


    #You dont need to specify which piece you are requesting ???
    def request_piece(self, peer):
        if peer.peer_choking:
            return
        for i in range(len(self.storage.my_bitfield)):
            if self.storage.my_bitfield[i] == 0 and peer.peer_bitfield[i] == 1:
                offset = 0
                block_length = 16384
                msg = struct.pack(">IBIII", 13, 6, i, offset, block_length)
                peer.socket.sendall(msg)
                return