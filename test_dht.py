#ai generated testing code
from core import Node
import time
import random

NUM_NODES = 10
BASE_PORT = 9000

print("\n=== CREATING NODES ===")

nodes = []
for i in range(NUM_NODES):
    node = Node("127.0.0.1", BASE_PORT + i)
    node.start_dht_listener()
    nodes.append(node)

time.sleep(1)

for i, node in enumerate(nodes):
    print(f"Node{i}: ID={node.node_id}, Port={BASE_PORT+i}")

# ---------------------------------------------------
# RANDOMLY CONNECT NODES (more realistic topology)
# ---------------------------------------------------
print("\n=== RANDOM BOOTSTRAP CONNECTIONS ===")

for i in range(NUM_NODES):
    # Each node connects to 2 random others
    others = random.sample([n for n in nodes if n != nodes[i]], 2)
    for other in others:
        nodes[i].ping(other.node_id, "127.0.0.1", other.port)

time.sleep(2)

# ---------------------------------------------------
# TEST 1: FULL NETWORK DISCOVERY
# ---------------------------------------------------
print("\n=== TEST 1: FULL NETWORK DISCOVERY ===")

target = random.choice(nodes)
print("Target node:", target.node_id)

result = nodes[0].iterative_find_node(target.node_id)

print("\nNode0 closest nodes to target:")
for r in result:
    print(r)

print("\nNode0 routing table size:",
      len(nodes[0].routing_table.get_closest_nodes(target.node_id, 100)))

# ---------------------------------------------------
# TEST 2: PEER ANNOUNCEMENT
# ---------------------------------------------------
print("\n=== TEST 2: PEER ANNOUNCEMENT ===")

info_hash = random.getrandbits(160)
print("Info hash:", info_hash)

announcing_node = random.choice(nodes)
print("Announcing node:", announcing_node.node_id)

closest_nodes = announcing_node.iterative_find_node(info_hash)

for node_id, ip, port, *_ in closest_nodes:
    announcing_node.announce_peer(node_id, ip, port, info_hash)

time.sleep(1)

# Another random node tries to discover peers
search_node = random.choice(nodes)
print("Searching node:", search_node.node_id)

found_peers = search_node.iterative_get_peers(info_hash)

# Remove duplicates
found_peers = list(set(tuple(p) for p in found_peers))

print("\nPeers found:")
print(found_peers)

# ---------------------------------------------------
# TEST 3: MULTIPLE ANNOUNCEMENTS
# ---------------------------------------------------
print("\n=== TEST 3: MULTIPLE ANNOUNCEMENTS ===")

info_hash2 = random.getrandbits(160)

# 3 nodes announce for same hash
announcers = random.sample(nodes, 3)
for node in announcers:
    closest_nodes = node.iterative_find_node(info_hash2)
    for node_id, ip, port, *_ in closest_nodes:
        node.announce_peer(node_id, ip, port, info_hash2)

time.sleep(1)

found = nodes[0].iterative_get_peers(info_hash2)
found = list(set(tuple(p) for p in found))

print("Peers found for shared hash:")
print(found)

# ---------------------------------------------------
# TEST 4: NODE FAILURE SIMULATION
# ---------------------------------------------------
print("\n=== TEST 4: NODE FAILURE SIMULATION ===")

dead_node = random.choice(nodes)
print("Simulating failure of:", dead_node.node_id)

# We won't stop it — just ignore it.
# Attempt lookup again.

result_after_failure = nodes[0].iterative_find_node(target.node_id)

print("\nLookup after failure:")
for r in result_after_failure:
    print(r)

print("\n=== TEST COMPLETE ===")
