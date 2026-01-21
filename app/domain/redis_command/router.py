from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.util.redis.client import redis_service
import json

router = APIRouter(prefix="/redis", tags=["redis"])


class RedisCommandRequest(BaseModel):
    """Redis 명령 요청 모델 - type, mapName, robotId 필수"""
    type: str  # "start", "return"
    mapName: str  # 맵 이름
    robotId: str  # 로봇 ID
    currentNode: int  # 현재 노드 (필수)
    finalNode: Optional[int] = None  # start에서만 사용


@router.post("/publish")
async def publish_command(request: RedisCommandRequest):
    """Redis 채널에 명령 발행 (단일 채널: robot:command)

    지원 명령: start, return

    Examples:
    - Start (일반 경로):
      {
        "type": "start",
        "mapName": "map1",
        "robotId": "robot1",
        "currentNode": 5,
        "finalNode": 10
      }

    - Return (복귀):
      {
        "type": "return",
        "mapName": "map1",
        "robotId": "robot1",
        "currentNode": 30
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
