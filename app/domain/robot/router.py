"""로봇 상태 조회 API 라우터"""
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, Depends

from app.domain.robot.robot_state_service import robot_state_service
from app.domain.robot.daily_stats_service import daily_stats_service
from app.domain.robot.robot_states import RobotOperationState
from app.util.redis.client import redis_service
from app.util.validators import validate_map_name

router = APIRouter(prefix="/robots", tags=["robots"])


@router.get("/{map_name}/{robot_id}")
async def get_robot_state(
    robot_id: str,
    map_name: str = Depends(validate_map_name)
):
    """특정 로봇의 상태 조회

    Args:
        map_name: 맵 이름 (smartfarm_ prefix 필수)
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
async def get_all_robots_in_map(map_name: str = Depends(validate_map_name)):
    """특정 맵의 모든 로봇 상태 조회

    Args:
        map_name: 맵 이름 (smartfarm_ prefix 필수)

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
async def delete_robot_state(
    robot_id: str,
    map_name: str = Depends(validate_map_name)
):
    """로봇 상태 삭제

    Args:
        map_name: 맵 이름 (smartfarm_ prefix 필수)
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


@router.post("/{map_name}/dummy")
async def create_dummy_data(map_name: str = Depends(validate_map_name)):
    """더미 로봇 데이터 생성 (로봇 1대, 2번 노드 대기 중)"""
    robot_id = "1"
    now = datetime.now()
    today = date.today()

    # 1. 로봇 상태 데이터
    state_key = f"robot:state:{map_name}:{robot_id}"
    redis_service.hset(state_key, "current_node", "2")
    redis_service.hset(state_key, "final_node", "2")
    redis_service.hset(state_key, "battery_state", "100")
    redis_service.hset(state_key, "charging_state", "0")
    redis_service.hset(state_key, "status", "idle")
    redis_service.hset(state_key, "updated_at", now.isoformat())

    # 2. 현재 운영 상태 추적
    current_state_key = f"robot:current_state:{map_name}:{robot_id}"
    redis_service.hset(current_state_key, "state", RobotOperationState.IDLE.value)
    redis_service.hset(current_state_key, "started_at", now.isoformat())

    # 3. 오늘 가동률 더미 통계 (8시간 기준)
    stats_key = f"robot:daily_stats:{map_name}:{robot_id}:{today.isoformat()}"
    redis_service.hset(stats_key, "working", "14400")       # 4시간
    redis_service.hset(stats_key, "charging", "3600")        # 1시간
    redis_service.hset(stats_key, "full_charge_idle", "7200") # 2시간
    redis_service.hset(stats_key, "idle", "3600")            # 1시간
    redis_service.expire(stats_key, 30 * 24 * 60 * 60)

    return {
        "message": f"Dummy data created for {robot_id} in {map_name}",
        "robot_id": robot_id,
        "state": "idle at node 2, battery 100%",
        "daily_stats": "working:4h, charging:1h, full_charge_idle:2h, idle:1h"
    }


@router.post("/{map_name}/dummy/stats/{target_date}")
async def create_dummy_daily_stats(
    target_date: str,
    map_name: str = Depends(validate_map_name)
):
    """특정 날짜의 가동률 더미데이터 생성

    Args:
        target_date: 날짜 (YYYY-MM-DD 형식)
        map_name: 맵 이름
    """
    try:
        parsed_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    robot_id = "1"
    stats_key = f"robot:daily_stats:{map_name}:{robot_id}:{parsed_date.isoformat()}"

    redis_service.hset(stats_key, "working", "14400")        # 4시간
    redis_service.hset(stats_key, "charging", "3600")         # 1시간
    redis_service.hset(stats_key, "full_charge_idle", "7200")  # 2시간
    redis_service.hset(stats_key, "idle", "3600")             # 1시간
    redis_service.expire(stats_key, 30 * 24 * 60 * 60)

    return {
        "message": f"Dummy daily stats created for {robot_id} in {map_name}",
        "date": parsed_date.isoformat(),
        "daily_stats": "working:4h, charging:1h, full_charge_idle:2h, idle:1h"
    }
