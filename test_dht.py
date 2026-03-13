from core import Node
import time

# Create nodes on different ports
node1 = Node("127.0.0.1", 6881)
node2 = Node("127.0.0.1", 6882, bootstrap_nodes=[("127.0.0.1", 6881)])
node3 = Node("127.0.0.1", 6883, bootstrap_nodes=[("127.0.0.1", 6881)])

nodes = [node1, node2, node3]

# Start listeners
for n in nodes:
    n.start_dht_listener()

# Bootstrap nodes
node1.bootstrap()
node2.bootstrap()
node3.bootstrap()

# Give network time to stabilize
time.sleep(2)

print("\nRouting tables after bootstrap:\n")

for n in nodes:
    print(f"Node {n.port} knows:")
    closest = n.routing_table.get_closest_nodes(n.node_id, 8)
    for node_id, ip, port, *_ in closest:
        print("   ", ip, port)
    print()

# Simulate torrent info hash
info_hash = 1234567890123456789012345678901234567890

# Node1 becomes a peer for the torrent
print("Node 6881 announcing peer...\n")
node1.iterative_announce_peer(info_hash)

time.sleep(1)

# Node3 tries to discover peers
print("Node 6883 searching for peers...\n")
peers = node3.iterative_get_peers(info_hash)

print("Peers discovered:")
print(peers)

# Keep program alive
while True:
    time.sleep(1)