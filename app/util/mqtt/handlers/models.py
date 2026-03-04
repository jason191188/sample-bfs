from pydantic import BaseModel


class PathPayload(BaseModel):
    current_node: int  # 현재 노드 ID
    final_node: int    # 목적지 노드 ID (0이면 복귀 시그널)


class BatteryPayload(BaseModel):
    battery_state: str  # 배터리 잔량 (%)
    battery_charging_state: int  # 충전 상태 (0: 미충전, 1: 충전중)
    robot_id: int
    map_name: str


class ArrivePayload(BaseModel):
    current_node: int  # 도착 노드 ID


class RemovePathPayload(BaseModel):
    current_node: int  # 해제할 노드 ID


class NextPayload(BaseModel):
    current_node: int  # 현재 노드 ID
    direction: str     # 진행 방향 (l, r, u, d)
