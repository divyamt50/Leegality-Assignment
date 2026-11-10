import heapq


def calculate_shortest_path(edges, start_node: str, end_node: str):
    if start_node == end_node:
        return 0.0, [start_node]

    adj_list = {}
    for edge in edges:
        if edge.source not in adj_list:
            adj_list[edge.source] = []
        adj_list[edge.source].append((edge.destination, edge.latency))

    min_heap = [(0.0, start_node, [start_node])]
    min_latency_seen = {start_node: 0.0}

    while min_heap:
        curr_latency, curr_node, path = heapq.heappop(min_heap)

        if curr_node == end_node:
            return round(curr_latency, 4), path

        if curr_latency > min_latency_seen.get(curr_node, float("inf")):
            continue

        for neighbor, edge_latency in adj_list.get(curr_node, []):
            new_latency = curr_latency + edge_latency
            if new_latency < min_latency_seen.get(neighbor, float("inf")):
                min_latency_seen[neighbor] = new_latency
                heapq.heappush(min_heap, (new_latency, neighbor, path + [neighbor]))

    return None, None