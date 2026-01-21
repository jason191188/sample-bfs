import json

from app.util.redis.client import redis_service

NODES_KEY = "nodes"


def init_node_data():
    if not redis_service.is_connected():
        return

    # 기존 데이터 확인
    existing = redis_service.hgetall(NODES_KEY)
    if existing:
        return

    # 1~60번 노드 생성 (1과 2만 위치 바꿈: [60] ← ... ← [3] ← [1] ← [2])
    # 순서: 2, 1, 3, 4, 5, ..., 60
    for node_id in range(1, 61):
        if node_id == 1:
            # 노드 1: 왼쪽은 3, 오른쪽은 2
            node_data = {
                "l": 3,
                "r": 2,
                "u": 0,
                "d": 0,
                "occupied": None,
            }
        elif node_id == 2:
            # 노드 2: 왼쪽은 1, 오른쪽은 0 (맨 오른쪽 끝)
            node_data = {
                "l": 1,
                "r": 0,
                "u": 0,
                "d": 0,
                "occupied": None,
            }
        elif node_id == 3:
            # 노드 3: 왼쪽은 4, 오른쪽은 1
            node_data = {
                "l": 4,
                "r": 1,
                "u": 0,
                "d": 0,
                "occupied": None,
            }
        else:
            # 나머지 노드들: 일반적인 순차 연결
            node_data = {
                "l": node_id + 1 if node_id < 60 else 0,
                "r": node_id - 1,
                "u": 0,
                "d": 0,
                "occupied": None,
            }
        redis_service.hset(NODES_KEY, str(node_id), json.dumps(node_data))



def get_all_nodes() -> dict:
    """모든 노드 데이터 조회"""
    raw_data = redis_service.hgetall(NODES_KEY)
    return {int(k): json.loads(v) for k, v in raw_data.items()}


def get_node(node_id: int) -> dict:
    """특정 노드 데이터 조회"""
    raw = redis_service.hget(NODES_KEY, str(node_id))
    if raw:
        return json.loads(raw)
    return None


def clear_nodes():
    """노드 데이터 초기화"""
    redis_service.delete(NODES_KEY)


def occupy_node(node_id: int, robot_id: str) -> bool:
    """노드 점유 설정

    Args:
        node_id: 점유할 노드 ID
        robot_id: 로봇 ID

    Returns:
        성공 여부 (이미 점유된 경우 False)
    """
    node = get_node(node_id)
    if not node:
        return False

    if node.get("occupied") is not None:
        return False  # 이미 점유됨

    node["occupied"] = robot_id
    redis_service.hset(NODES_KEY, str(node_id), json.dumps(node))
    return True


def release_node(node_id: int, robot_id: str = None) -> bool:
    """노드 점유 해제

    Args:
        node_id: 해제할 노드 ID
        robot_id: 로봇 ID (지정 시 해당 로봇이 점유한 경우만 해제)

    Returns:
        성공 여부
    """
    node = get_node(node_id)
    if not node:
        return False

    # robot_id가 지정된 경우, 해당 로봇이 점유한 노드인지 확인
    if robot_id and node.get("occupied") != robot_id:
        return False

    node["occupied"] = None
    redis_service.hset(NODES_KEY, str(node_id), json.dumps(node))
    return True


def get_occupied_nodes() -> dict[int, str]:
    """점유된 노드 목록 조회

    Returns:
        {node_id: robot_id} 형태의 딕셔너리
    """
    all_nodes = get_all_nodes()
    return {
        node_id: node["occupied"]
        for node_id, node in all_nodes.items()
        if node.get("occupied") is not None
    }


def release_robot_nodes(robot_id: str) -> int:
    """특정 로봇이 점유한 모든 노드 해제

    Args:
        robot_id: 로봇 ID

    Returns:
        해제된 노드 수
    """
    all_nodes = get_all_nodes()
    released_count = 0

    for node_id, node in all_nodes.items():
        if node.get("occupied") == robot_id:
            node["occupied"] = None
            redis_service.hset(NODES_KEY, str(node_id), json.dumps(node))
            released_count += 1

    return released_count
