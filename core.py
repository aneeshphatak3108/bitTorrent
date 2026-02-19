import time
import random
import json
import socket
import threading

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
        self.nodes = []  # list of (node_id, ip, port, last_seen)

    def find_node(self, node_id):
        for node in self.nodes:
            if node[0] == node_id:
                return node
        return None

    def remove_node(self, node_id):
        self.nodes = [n for n in self.nodes if n[0] != node_id]

    def add_node(self, node_info, ping_function):
        """
        node_info = (node_id, ip, port)
        ping_function(ip, port) should return True if alive
        """
        node_id, ip, port = node_info
        existing = self.find_node(node_id)
        # Case 1: Node already exists ---> move to end (most recently seen)
        if existing:
            self.nodes.remove(existing)
            self.nodes.append((node_id, ip, port, time.time()))
            return

        # Case 2: Bucket not full
        if len(self.nodes) < self.k:
            self.nodes.append((node_id, ip, port, time.time()))
            return

        # Case 3: Bucket full ---> ping oldest node
        oldest = self.nodes[0]
        oldest_id, oldest_ip, oldest_port, _ = oldest

        if ping_function(oldest_ip, oldest_port):
            # Old node alive ---> keep it, discard new node
            return
        else:
            # Old node dead ---> replace it
            self.nodes.pop(0)
            self.nodes.append((node_id, ip, port, time.time()))



class RoutingTable:
    def __init__(self, node_id, k=8, id_bits=160):
        self.node_id = node_id
        self.k = k
        self.id_bits = id_bits
        self.buckets = [KBucket(k) for _ in range(id_bits)] #creates 160 buckets, each bucket corresponds to nodes whose XOR distance has highest differing bit at that position.

    def get_bucket_index(self, other_id):
        distance = self.node_id ^ other_id
        return distance.bit_length() - 1

    def add_node(self, node_id, ip, port, ping_function):
        index = self.get_bucket_index(node_id)
        if index >= 0:
            self.buckets[index].add_node((node_id, ip, port), ping_function)

    def get_closest_nodes(self, target_id, k):
        all_nodes = []
        for bucket in self.buckets:
            all_nodes.extend(bucket.nodes)
        all_nodes.sort(key=lambda node: node[0] ^ target_id)
        return all_nodes[:k]


class Node:
    def __init__(self, ip, port, bootstrap_nodes=None):
        self.ip = ip
        self.port = port
        self.node_id = random.getrandbits(160)
        #DHT stuff
        self.routing_table = RoutingTable(self.node_id)
        self.local_storage = {}  # info_hash -> [(ip, port)]
        self.bootstrap_nodes = bootstrap_nodes or []

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))

    #Core RPC function....everyting is built on top of this helper function
    def send_rpc(self, ip, port, message):
        try:
            self.sock.sendto(json.dumps(message).encode(), (ip, port))
            self.sock.settimeout(2)
            data, _ = self.sock.recvfrom(4096)
            return json.loads(data.decode())
        except:
            return None


    #OUTGOING RPC (like client, initiates communication)
    def ping(self, node_id, ip, port):
        response = self.send_rpc(ip, port, {
            "type": "ping",
            "node_id": self.node_id
        })
        if response:
            self.routing_table.add_node(node_id, ip, port, self.ping_node)
        return response

    def find_node(self, node_id, ip, port, target_id):
        response = self.send_rpc(ip, port, {
            "type": "find_node",
            "node_id": self.node_id,
            "target_id": target_id
        })
        if response and "nodes" in response:
            for n_id, n_ip, n_port in response["nodes"]:
                self.routing_table.add_node(n_id, n_ip, n_port, self.ping_node)
        return response

    def get_peers(self, node_id, ip, port, info_hash):
        response = self.send_rpc(ip, port, {
            "type": "get_peers",
            "node_id": self.node_id,
            "info_hash": info_hash
        })
        #if "values" was in response then the peers are found....if "nodes" then this means i just got some nodes who were closer to the info_hash
        #so just add them to my routing table
        if response and "nodes" in response:
            for n_id, n_ip, n_port in response["nodes"]:
                self.routing_table.add_node(n_id, n_ip, n_port, self.ping_node)
        return response

    def announce_peer(self, node_id, ip, port, info_hash):
        return self.send_rpc(ip, port, {
            "type": "announce_peer",
            "node_id": self.node_id,
            "info_hash": info_hash,
            "port": self.port
        })



    #INCOMING RPCs (like server, gives response)
    def handle_ping(self, sender_node_id, sender_ip, sender_port):
        self.routing_table.add_node(sender_node_id, sender_ip, sender_port, self.ping_node)
        return {"node_id": self.node_id}

    def handle_find_node(self, sender_node_id, sender_ip, sender_port, target_id):
        self.routing_table.add_node(sender_node_id, sender_ip, sender_port, self.ping_node)
        closest = self.routing_table.get_closest_nodes(
            target_id, self.routing_table.k
        )
        return {
            "nodes": [(n[0], n[1], n[2]) for n in closest]
        }

    def handle_get_peers(self, sender_node_id, sender_ip, sender_port, info_hash):
        self.routing_table.add_node(sender_node_id, sender_ip, sender_port, self.ping_node)
        if info_hash in self.local_storage:
            return {"values": self.local_storage[info_hash]}
        else:
            closest = self.routing_table.get_closest_nodes(
                info_hash, self.routing_table.k
            )
            return {"nodes": [(n[0], n[1], n[2]) for n in closest]}


    def handle_announce_peer(self, sender_node_id, sender_ip, sender_port, info_hash, peer_port):
        self.routing_table.add_node(sender_node_id, sender_ip, sender_port, self.ping_node)
        closest = self.routing_table.get_closest_nodes(
            info_hash, self.routing_table.k
        )
        my_distance = self.node_id ^ info_hash
        farthest = max((n[0] ^ info_hash) for n in closest) if closest else float('inf')
        if my_distance <= farthest:
            if info_hash not in self.local_storage:
                self.local_storage[info_hash] = []
            peer_entry = (sender_ip, peer_port)
            if peer_entry not in self.local_storage[info_hash]:
                self.local_storage[info_hash].append(peer_entry)
        return {"status": "ok"}



    #Looks at the recieved message and decides which function to call
    def handle_incoming(self, data, addr):
        message = json.loads(data.decode())
        sender_ip, sender_port = addr
        sender_node_id = message.get("node_id")

        if message["type"] == "ping":
            response = self.handle_ping(sender_node_id, sender_ip, sender_port)

        elif message["type"] == "find_node":
            response = self.handle_find_node(
                sender_node_id, sender_ip, sender_port,
                message["target_id"]
            )

        elif message["type"] == "get_peers":
            response = self.handle_get_peers(
                sender_node_id, sender_ip, sender_port,
                message["info_hash"]
            )

        elif message["type"] == "announce_peer":
            response = self.handle_announce_peer(
                sender_node_id, sender_ip, sender_port,
                message["info_hash"],
                message["port"]
            )
        else:
            return
        self.sock.sendto(json.dumps(response).encode(), addr)

    def start_dht_listener(self):
        def listen():
            while True:
                data, addr = self.sock.recvfrom(4096)
                self.handle_incoming(data, addr)

        thread = threading.Thread(target=listen, daemon=True)
        thread.start()


    #Iterative lookup, alpha decides the breadth
    def iterative_find_node(self, target_id, alpha=3):
        queried = set()
        closest = self.routing_table.get_closest_nodes(target_id, self.routing_table.k)
        while True:
            new_nodes = []
            to_query = [n for n in closest if n[0] not in queried][:alpha]
            if not to_query:
                break
            for node_id, ip, port in to_query:
                queried.add(node_id)
                response = self.find_node(node_id, ip, port, target_id)
                if response and "nodes" in response:
                    new_nodes.extend(response["nodes"])

            for n_id, n_ip, n_port in new_nodes:
                self.routing_table.add_node(n_id, n_ip, n_port, self.ping_node)
            updated = self.routing_table.get_closest_nodes(target_id, self.routing_table.k)
            if updated == closest:
                break
            closest = updated
        return closest

    def iterative_get_peers(self, info_hash, alpha=3):
        queried = set()
        closest = self.routing_table.get_closest_nodes(info_hash, self.routing_table.k)
        found_peers = []
        while True:
            to_query = [n for n in closest if n[0] not in queried][:alpha]
            if not to_query:
                break

            for node_id, ip, port in to_query:
                queried.add(node_id)
                response = self.get_peers(node_id, ip, port, info_hash)
                if not response:
                    continue
                if "values" in response:
                    found_peers.extend(response["values"])
                if "nodes" in response:
                    for n_id, n_ip, n_port in response["nodes"]:
                        self.routing_table.add_node(n_id, n_ip, n_port, self.ping_node)

            updated = self.routing_table.get_closest_nodes(info_hash, self.routing_table.k)
            if updated == closest:
                break
            closest = updated
        return found_peers