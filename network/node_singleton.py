from collections import defaultdict
import threading

node_instance = None
signal_queues = defaultdict(list)
signal_lock = threading.Lock()