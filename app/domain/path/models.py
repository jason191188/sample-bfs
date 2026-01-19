from pydantic import BaseModel


class PathRequest(BaseModel):
    start: int  # 시작 노드 ID
    end: int    # 도착 노드 ID


class PathResponse(BaseModel):
    path: str  # 형식: {목적지}!{출발지},{방향}/{노드},{방향}/...
    success: bool
    message: str
