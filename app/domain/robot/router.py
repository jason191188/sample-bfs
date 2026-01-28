"""로봇 상태 조회 API 라우터"""
from fastapi import APIRouter, HTTPException

from app.domain.robot.robot_state_service import robot_state_service

router = APIRouter(prefix="/robots", tags=["robots"])


@router.get("/{map_name}/{robot_id}")
async def get_robot_state(map_name: str, robot_id: str):
    """특정 로봇의 상태 조회

    Args:
        map_name: 맵 이름
        robot_id: 로봇 ID

    Returns:
        로봇 상태 정보
    """
    state = robot_state_service.get_robot_state(map_name, robot_id)

    if not state:
        raise HTTPException(status_code=404, detail=f"Robot {robot_id} not found in map {map_name}")

    return {
        "map_name": map_name,
        "robot_id": robot_id,
        "state": state
    }


@router.get("/{map_name}")
async def get_all_robots_in_map(map_name: str):
    """특정 맵의 모든 로봇 상태 조회

    Args:
        map_name: 맵 이름

    Returns:
        맵 내 모든 로봇의 상태 정보
    """
    robots = robot_state_service.get_all_robots_in_map(map_name)

    return {
        "map_name": map_name,
        "robot_count": len(robots),
        "robots": robots
    }


@router.delete("/{map_name}/{robot_id}")
async def delete_robot_state(map_name: str, robot_id: str):
    """로봇 상태 삭제

    Args:
        map_name: 맵 이름
        robot_id: 로봇 ID

    Returns:
        삭제 결과
    """
    success = robot_state_service.delete_robot_state(map_name, robot_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete robot state")

    return {
        "message": f"Robot {robot_id} state deleted from map {map_name}",
        "success": True
    }
