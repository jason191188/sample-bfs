from collections import deque

from app.util.redis.init_data import get_all_nodes


def bfs(map_name: str, start: int, end: int) -> tuple[list[int], list[str]]:
    """BFS를 이용한 최단 경로 탐색 (Redis 노드 데이터 기반)

    Args:
        map_name: 맵 이름
        start: 시작 노드 ID
        end: 목적지 노드 ID

    Returns:
        (경로 노드 리스트, 방향 리스트)
    """
    nodes = get_all_nodes(map_name)

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


def cut_path(map_name: str, path: list[int], directions: list[str], robot_id: str) -> tuple[list[int], list[str]]:
    """경로를 점유되지 않은 노드까지 자르기

    Args:
        map_name: 맵 이름
        path: 전체 경로 노드 리스트
        directions: 전체 방향 리스트
        robot_id: 로봇 ID

    Returns:
        (잘린 경로 노드 리스트, 잘린 방향 리스트)
    """
    if not path:
        return [], []

    nodes = get_all_nodes(map_name)
    cut_index = len(path)  # 기본값: 전체 경로

    # 시작 노드(path[0])는 제외하고 경로 검사
    for i in range(1, len(path)):
        node_id = path[i]
        node_data = nodes.get(node_id)

        if not node_data:
            cut_index = i
            break

        occupied_by = node_data.get("occupied")

        # 다른 로봇이 점유한 노드를 만나면 그 직전까지만 경로로 설정
        if occupied_by is not None and occupied_by != robot_id:
            cut_index = i
            break

    # 경로와 방향을 cut_index까지만 자르기
    cut_path_result = path[:cut_index]
    cut_directions_result = directions[:cut_index]

    return cut_path_result, cut_directions_result


def format_path(end: int, start: int, path: list[int], directions: list[str]) -> str:
    """경로를 문자열 형식으로 변환: {목적지}!{출발지},{방향}/{노드},{방향}/... (목적지 제외)"""
    result = f"{end}!{start},{directions[0]}/"
    # 마지막 목적지 노드 제외 (len(path) - 1)
    for i in range(1, len(path) - 1):
        result += f"{path[i]},{directions[i]}/"
    return result
