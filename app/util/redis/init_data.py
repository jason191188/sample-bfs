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

    # 1~60번 노드 생성 (일렬 연결: 1번=오른쪽 끝, 60번=왼쪽 끝)
    # [60] ← [59] ← ... ← [2] ← [1]
    for node_id in range(1, 61):
        node_data = {
            "l": node_id + 1 if node_id < 60 else 0,  # 왼쪽 노드 (60번은 없음)
            "r": node_id - 1 if node_id > 1 else 0,   # 오른쪽 노드 (1번은 없음)
            "u": 0,
            "d": 0,
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
