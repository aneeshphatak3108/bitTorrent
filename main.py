from core import Node
import time
import random

bootstrap_nodes = [] #these must be hardcoded

node = Node("127.0.0.1", 6881, bootstrap_nodes)

node.start_dht_listener()
node.bootstrap()
node.start_dht_maintenance()