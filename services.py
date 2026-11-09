import heapq

def find_shortest_path(edges, start: str, end: str):
    graph = {}

    for edge in edges:
        graph.setdefault(edge.source, []).append((edge.destination, edge.latency))

    queue = [(0.0, start, [start])]
    best_latency = {start: 0.0}

    while queue:
        latency, current, path = heapq.heappop(queue)

        if current == end:
            return round(latency, 4), path

        for neighbor, weight in graph.get(current, []):
            new_latency = latency + weight
            if new_latency < best_latency.get(neighbor, float("inf")):
                best_latency[neighbor] = new_latency
                heapq.heappush(queue, (new_latency, neighbor, path + [neighbor]))

    return None, None  