from pydantic import BaseModel


class PathPayload(BaseModel):
    current_node: int
    final_node: int


class BatteryPayload(BaseModel):
    battery_state: str  # 배터리 잔량 (%)
    battery_charging_state: int  # 충전 상태 (0: 미충전, 1: 충전중)
    robot_id: int
    map_name: str


class ArrivePayload(BaseModel):
    current_node: int  # 도착 노드


class RemovePathPayload(BaseModel):
    current_node: int  # 해제할 노드
