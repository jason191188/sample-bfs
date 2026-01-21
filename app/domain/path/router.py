from fastapi import APIRouter, HTTPException

from app.config.settings import settings
from app.domain.path.models import (
    PathRequest,
    PathResponse,
    OccupyNodeRequest,
    ReleaseNodeRequest,
    NodeOccupationResponse,
    OccupiedNodesResponse,
)
from app.domain.path.service import bfs, cut_path, format_path
from app.util.mqtt.client import mqtt_service
from app.util.redis.init_data import (
    occupy_node,
    release_node,
    get_occupied_nodes,
    release_robot_nodes,
)

router = APIRouter(prefix="/path", tags=["path"])


@router.post("", response_model=PathResponse)
async def find_path(request: PathRequest):
    """BFS로 경로를 찾고 MQTT로 전송 (Redis 노드 데이터 기반)"""
    # 1. BFS로 전체 최단 경로 계산
    path, directions = bfs(request.start, request.end)

    if not path:
        raise HTTPException(status_code=404, detail="경로를 찾을 수 없습니다")

    # 2. robot_id가 제공된 경우, 점유된 노드를 고려하여 경로를 자름
    if request.robot_id:
        path, directions = cut_path(path, directions, request.robot_id)

        # 경로가 잘려서 시작 노드만 남은 경우
        if len(path) <= 1:
            raise HTTPException(
                status_code=409, detail="다른 로봇이 경로를 점유하고 있어 이동할 수 없습니다"
            )

    # 3. 경로 문자열 생성
    actual_end = path[-1]  # 실제 도착 노드 (잘린 경우 원래 목적지와 다를 수 있음)
    path_str = format_path(actual_end, request.start, path, directions)

    # 4. MQTT로 경로 전송
    if mqtt_service.publish(settings.mqtt.pub_topic, path_str):
        message = "경로 전송 완료"
    else:
        message = "경로 찾음 (MQTT 미연결)"

    # 경로가 잘린 경우 메시지에 알림 추가
    if request.robot_id and actual_end != request.end:
        message += f" (점유된 노드로 인해 노드 {actual_end}까지만 이동 가능)"

    return PathResponse(path=path_str, success=True, message=message)


@router.post("/occupy", response_model=NodeOccupationResponse)
async def occupy_node_endpoint(request: OccupyNodeRequest):
    """노드 점유"""
    success = occupy_node(request.node_id, request.robot_id)

    if success:
        return NodeOccupationResponse(
            success=True, message=f"노드 {request.node_id} 점유 완료"
        )
    else:
        raise HTTPException(
            status_code=409, detail=f"노드 {request.node_id}는 이미 점유되었거나 존재하지 않습니다"
        )


@router.post("/release", response_model=NodeOccupationResponse)
async def release_node_endpoint(request: ReleaseNodeRequest):
    """노드 점유 해제"""
    success = release_node(request.node_id, request.robot_id)

    if success:
        return NodeOccupationResponse(
            success=True, message=f"노드 {request.node_id} 해제 완료"
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=f"노드 {request.node_id}를 해제할 수 없습니다 (존재하지 않거나 다른 로봇이 점유 중)",
        )


@router.get("/occupied", response_model=OccupiedNodesResponse)
async def get_occupied_nodes_endpoint():
    """점유된 노드 목록 조회"""
    occupied = get_occupied_nodes()
    return OccupiedNodesResponse(occupied_nodes=occupied)


@router.delete("/robot/{robot_id}", response_model=NodeOccupationResponse)
async def release_robot_nodes_endpoint(robot_id: str):
    """특정 로봇이 점유한 모든 노드 해제"""
    count = release_robot_nodes(robot_id)
    return NodeOccupationResponse(
        success=True, message=f"로봇 {robot_id}의 노드 {count}개 해제 완료"
    )
