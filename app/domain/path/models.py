from pydantic import BaseModel


class PathRequest(BaseModel):
    start: int  # 시작 노드 ID
    end: int    # 도착 노드 ID
    robot_id: str = None  # 로봇 ID (옵션, 점유 노드 회피용)


class PathResponse(BaseModel):
    path: str  # 형식: {목적지}!{출발지},{방향}/{노드},{방향}/...
    success: bool
    message: str


class OccupyNodeRequest(BaseModel):
    node_id: int  # 점유할 노드 ID
    robot_id: str  # 로봇 ID


class ReleaseNodeRequest(BaseModel):
    node_id: int  # 해제할 노드 ID
    robot_id: str = None  # 로봇 ID (옵션, 지정 시 해당 로봇이 점유한 경우만 해제)


class NodeOccupationResponse(BaseModel):
    success: bool
    message: str


class OccupiedNodesResponse(BaseModel):
    occupied_nodes: dict[int, str]  # {node_id: robot_id}
