from fastapi import APIRouter, HTTPException

from app.config.settings import settings
from app.domain.path.models import PathRequest, PathResponse
from app.domain.path.service import bfs, format_path
from app.util.mqtt.client import mqtt_service

router = APIRouter(prefix="/path", tags=["path"])


@router.post("", response_model=PathResponse)
async def find_path(request: PathRequest):
    """BFS로 경로를 찾고 MQTT로 전송 (Redis 노드 데이터 기반)"""
    path, directions = bfs(request.start, request.end)

    if not path:
        raise HTTPException(status_code=404, detail="경로를 찾을 수 없습니다")

    # 경로 문자열 생성
    path_str = format_path(request.end, request.start, path, directions)

    # MQTT로 경로 전송
    if mqtt_service.publish(settings.mqtt.pub_topic, path_str):
        message = "경로 전송 완료"
    else:
        message = "경로 찾음 (MQTT 미연결)"

    return PathResponse(path=path_str, success=True, message=message)
