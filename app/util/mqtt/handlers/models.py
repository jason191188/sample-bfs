from typing import Optional
from pydantic import BaseModel


class PathPayload(BaseModel):
    current_node: str  # "2" (일반) 또는 "2-1" (서브노드)
    final_node: str    # "10" (일반) 또는 "2-1" (서브노드)


class BatteryPayload(BaseModel):
    battery_state: str  # 배터리 잔량 (%)
    battery_charging_state: int  # 충전 상태 (0: 미충전, 1: 충전중)
    robot_id: int
    map_name: str


class ArrivePayload(BaseModel):
    current_node: str  # 도착 노드 ("2" 또는 "2-1")


class RemovePathPayload(BaseModel):
    current_node: str  # 해제할 노드 ("2" 또는 "2-1")


class NextPayload(BaseModel):
    current_node: str                    # 현재 노드 ("2" 또는 "2-1")
    sub_position: Optional[int] = None   # 서브 위치 (0-4), 없으면 노드 단위
    direction: str                       # 진행 방향 (l, r, u, d)
