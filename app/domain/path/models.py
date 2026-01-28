from pydantic import BaseModel, field_validator


class PathRequest(BaseModel):
    map_name: str = "default"  # 맵 이름
    start: int  # 시작 노드 ID
    end: int    # 도착 노드 ID
    robot_id: str = None  # 로봇 ID (옵션, 점유 노드 회피용)

    @field_validator('map_name')
    @classmethod
    def validate_map_name(cls, v: str) -> str:
        """맵 이름 검증 - smartfarm_ prefix 필수"""
        if not v.startswith('smartfarm_'):
            raise ValueError(f"Map name must start with 'smartfarm_'. Got: '{v}'")
        return v


class PathResponse(BaseModel):
    path: str  # 형식: {목적지}!{출발지},{방향}/{노드},{방향}/...
    success: bool
    message: str


class OccupyNodeRequest(BaseModel):
    map_name: str = "default"  # 맵 이름
    node_id: int  # 점유할 노드 ID
    robot_id: str  # 로봇 ID

    @field_validator('map_name')
    @classmethod
    def validate_map_name(cls, v: str) -> str:
        """맵 이름 검증 - smartfarm_ prefix 필수"""
        if not v.startswith('smartfarm_'):
            raise ValueError(f"Map name must start with 'smartfarm_'. Got: '{v}'")
        return v


class ReleaseNodeRequest(BaseModel):
    map_name: str = "default"  # 맵 이름
    node_id: int  # 해제할 노드 ID
    robot_id: str = None  # 로봇 ID (옵션, 지정 시 해당 로봇이 점유한 경우만 해제)

    @field_validator('map_name')
    @classmethod
    def validate_map_name(cls, v: str) -> str:
        """맵 이름 검증 - smartfarm_ prefix 필수"""
        if not v.startswith('smartfarm_'):
            raise ValueError(f"Map name must start with 'smartfarm_'. Got: '{v}'")
        return v


class NodeOccupationResponse(BaseModel):
    success: bool
    message: str


class OccupiedNodesResponse(BaseModel):
    occupied_nodes: dict[int, str]  # {node_id: robot_id}
