from pydantic import BaseModel


class PathPayload(BaseModel):
    current_node: int
    final_node: int


class BatteryPayload(BaseModel):
    level: int  # 배터리 잔량 (%)


class ArrivePayload(BaseModel):
    node: int  # 도착 노드
