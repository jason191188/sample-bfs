from collections import deque

from app.util.redis.init_data import get_all_nodes


def bfs(start: int, end: int) -> tuple[list[int], list[str]]:
    """BFS를 이용한 최단 경로 탐색 (Redis 노드 데이터 기반)"""
    nodes = get_all_nodes()

    if not nodes:
        return [], []

    if start not in nodes or end not in nodes:
        return [], []

    queue = deque([(start, [start], [])])  # (현재 노드, 경로, 방향들)
    visited = {start}

    while queue:
        current, path, directions = queue.popleft()

        if current == end:
            return path, directions

        node = nodes[current]

        # 각 방향 탐색 (l, r, u, d)
        for direction, next_node in [("l", node["l"]), ("r", node["r"]), ("u", node["u"]), ("d", node["d"])]:
            if next_node != 0 and next_node not in visited and next_node in nodes:
                visited.add(next_node)
                queue.append((next_node, path + [next_node], directions + [direction]))

    return [], []


def format_path(end: int, start: int, path: list[int], directions: list[str]) -> str:
    """경로를 문자열 형식으로 변환: {목적지}!{출발지},{방향}/{노드},{방향}/... (목적지 제외)"""
    result = f"{end}!{start},{directions[0]}/"
    # 마지막 목적지 노드 제외 (len(path) - 1)
    for i in range(1, len(path) - 1):
        result += f"{path[i]},{directions[i]}/"
    return result
