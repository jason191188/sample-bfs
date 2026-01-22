from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.util.redis.client import redis_service
import json

router = APIRouter(prefix="/redis", tags=["redis"])


class RedisCommandRequest(BaseModel):
    """Redis 명령 요청 모델 - type, mapName, robotId만 필요

    - 현재 노드: Redis에 저장된 로봇 상태에서 자동 조회
    - 다음 노드: 현재 노드의 왼쪽(l) 방향 노드로 자동 결정
    """
    type: str  # "start", "return"
    mapName: str  # 맵 이름
    robotId: str  # 로봇 ID


@router.post("/publish")
async def publish_command(request: RedisCommandRequest):
    """Redis 채널에 명령 발행 (단일 채널: robot:command)

    지원 명령: start, return

    동작 방식:
    - start: 현재 노드의 왼쪽(l) 방향 노드를 MQTT server/button으로 전송
    - return: final_node: 0을 MQTT server/button으로 전송 (복귀 시그널)

    MQTT 토픽: {mapName}/{robotId}/server/button
    Payload: {"final_node": 10} 또는 {"final_node": 0}

    Examples:
    - Start (왼쪽 방향 노드를 final_node로 전송):
      {
        "type": "start",
        "mapName": "map1",
        "robotId": "robot1"
      }

    - Return (final_node: 0 전송):
      {
        "type": "return",
        "mapName": "map1",
        "robotId": "robot1"
      }
    """
    channel = "robot:command"
    message = json.dumps(request.model_dump(exclude_none=True))

    if redis_service.publish(channel, message):
        return {
            "success": True,
            "message": f"Command published to channel: {channel}",
            "channel": channel,
            "data": request.model_dump(exclude_none=True)
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to publish command (Redis not connected)"
        )
