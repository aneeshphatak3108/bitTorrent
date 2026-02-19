import time
import random

#this is going to be a part of every node object (a dictionary of the peer-list peer_id ---> peerconnection)
class PeerConnection:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.socket = None
        self.peer_id = None
        self.peer_bitfield = None
        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False

        self.download_rate = 0
        self.upload_rate = 0

        self.pending_requests = {}  #key-value pairs stored as (piece, block)--->timestamp
        self.last_active = time.time()



#again, this is part of node object
#does 3 jobs ->
#1)track which pieces you own
#2)track partial download progress
#3)verify downloaded pieces
class Storage:
    def __init__(self, total_pieces, piece_length, piece_hashes):
        self.total_pieces = total_pieces
        self.piece_length = piece_length
        self.piece_hashes = piece_hashes  #[SHA1(piece_0), SHA1(piece_1), ..., SHA1(piece_1023)]
        self.my_bitfield = [0] * total_pieces
        self.block_status = {}  # piece_index -> list of block states
        '''
        0 is not rquested, 1 is requested, 2 is recieved
        the information that to whom i have requested the block is stored in PeerConection object
        {
                5: [2, 2, 1, 0, 0, 0],
                12: [2, 2, 2, 2, 2, 2]
        }
        '''
    def initialize_piece(self, piece_index, num_blocks):
        self.block_status[piece_index] = [0] * num_blocks

    def mark_block_received(self, piece_index, block_index):
        self.block_status[piece_index][block_index] = 2

    def is_piece_complete(self, piece_index):
        return all(b == 2 for b in self.block_status[piece_index])


class KBucket:
    def __init__(self, k):
        self.k = k
        self.nodes = []  # list of (node_id, ip, port)

    def add_node(self, node_info):
        if node_info not in self.nodes:
            if len(self.nodes) < self.k:
                self.nodes.append(node_info)


class RoutingTable:
    def __init__(self, node_id, k=8, id_bits=160):
        self.node_id = node_id
        self.k = k
        self.id_bits = id_bits
        self.buckets = [KBucket(k) for _ in range(id_bits)] #creates 160 buckets, each bucket corresponds to nodes whose XOR distance has highest differing bit at that position.
    def get_bucket_index(self, other_id):
        distance = self.node_id ^ other_id
        return distance.bit_length() - 1

    def add_node(self, node_id, ip, port):
        index = self.get_bucket_index(node_id)
        if index >= 0:
            self.buckets[index].add_node((node_id, ip, port))


class Node:
    def __init__(self, ip, port, bootstrap_nodes=None):
        self.ip = ip
        self.port = port
        self.node_id = random.getrandbits(160) #node_id and peer_id is kept same in our case
        self.peers = {}  #peer_id -> PeerConnection
        self.storage = None  #will assign after loading torrent

        # DHT layer
        self.routing_table = RoutingTable(self.node_id)
        ''' Something like this
        {
            info_hash_A: [("127.0.0.1", 8001), ("127.0.0.1", 8002)],
            info_hash_B: [("127.0.0.1", 8010)]
        }
        '''
        self.local_storage = {}  # info_hash -> list of (ip, port)
        self.bootstrap_nodes = bootstrap_nodes or []