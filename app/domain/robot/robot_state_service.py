"""로봇 상태 관리 서비스 - Redis에 로봇 데이터 저장/조회"""
import json
from typing import Optional
from datetime import datetime

from app.util.redis.client import redis_service


class RobotStateService:
    """로봇 상태를 Redis Hash에 저장하는 서비스"""

    def _get_robot_key(self, map_name: str, robot_id: str) -> str:
        """로봇 상태 저장 키 생성

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID

        Returns:
            Redis 키 (예: "robot:state:map1:robot1")
        """
        return f"robot:state:{map_name}:{robot_id}"

    def update_position(self, map_name: str, robot_id: str, current_node: int, final_node: int = None) -> bool:
        """로봇 위치 정보 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            current_node: 현재 노드
            final_node: 목적지 노드 (Optional)

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)

        redis_service.hset(key, "current_node", str(current_node))
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        if final_node is not None:
            redis_service.hset(key, "final_node", str(final_node))

        return True

    def update_battery(self, map_name: str, robot_id: str, battery_level: int) -> bool:
        """로봇 배터리 정보 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            battery_level: 배터리 잔량 (%)

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)

        redis_service.hset(key, "battery_level", str(battery_level))
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        return True

    def update_status(self, map_name: str, robot_id: str, status: str, node: int = None) -> bool:
        """로봇 상태 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            status: 상태 (예: "idle", "moving", "arrived", "charging")
            node: 관련 노드 (Optional)

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)

        redis_service.hset(key, "status", status)
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        if node is not None:
            redis_service.hset(key, "current_node", str(node))

        return True

    def get_robot_state(self, map_name: str, robot_id: str) -> Optional[dict]:
        """로봇 상태 조회

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID

        Returns:
            로봇 상태 딕셔너리 또는 None
        """
        key = self._get_robot_key(map_name, robot_id)
        state = redis_service.hgetall(key)

        if not state:
            return None

        # 숫자 필드는 int로 변환
        if "current_node" in state:
            state["current_node"] = int(state["current_node"])
        if "final_node" in state:
            state["final_node"] = int(state["final_node"])
        if "battery_level" in state:
            state["battery_level"] = int(state["battery_level"])

        return state

    def get_all_robots_in_map(self, map_name: str) -> dict[str, dict]:
        """특정 맵의 모든 로봇 상태 조회

        Args:
            map_name: 맵 이름

        Returns:
            {robot_id: 상태} 딕셔너리
        """
        pattern = f"robot:state:{map_name}:*"
        robots = {}

        if not redis_service.client:
            return robots

        # 패턴 매칭으로 모든 키 찾기
        for key in redis_service.client.scan_iter(match=pattern):
            # 키에서 robot_id 추출
            robot_id = key.split(":")[-1]
            state = redis_service.hgetall(key)

            if state:
                # 숫자 필드 변환
                if "current_node" in state:
                    state["current_node"] = int(state["current_node"])
                if "final_node" in state:
                    state["final_node"] = int(state["final_node"])
                if "battery_level" in state:
                    state["battery_level"] = int(state["battery_level"])

                robots[robot_id] = state

        return robots

    def delete_robot_state(self, map_name: str, robot_id: str) -> bool:
        """로봇 상태 삭제

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)
        return redis_service.delete(key)


robot_state_service = RobotStateService()
