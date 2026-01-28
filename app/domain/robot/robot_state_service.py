"""로봇 상태 관리 서비스 - Redis에 로봇 데이터 저장/조회"""
import json
from typing import Optional
from datetime import datetime

from app.util.redis.client import redis_service
from app.domain.robot.robot_states import RobotOperationState
from app.domain.robot.daily_stats_service import daily_stats_service


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

    def _check_and_update_operation_state(
        self,
        map_name: str,
        robot_id: str,
        current_node: int = None,
        battery_level: float = None,
        charging_state: int = None
    ) -> None:
        """운영 상태 변화 감지 및 일일 통계 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            current_node: 현재 노드 (업데이트된 경우)
            battery_level: 배터리 잔량 (업데이트된 경우)
            charging_state: 충전 상태 (업데이트된 경우)
        """
        # 현재 저장된 상태 조회
        state = self.get_robot_state(map_name, robot_id)
        if not state:
            return

        # 최신 값으로 업데이트
        if current_node is not None:
            state["current_node"] = current_node
        if battery_level is not None:
            state["battery_level"] = battery_level
        if charging_state is not None:
            state["charging_state"] = charging_state

        # 필수 필드 확인
        if "current_node" not in state or "battery_level" not in state or "charging_state" not in state:
            return

        # 현재 운영 상태 결정
        new_state = RobotOperationState.determine_state(
            state["current_node"],
            state["charging_state"],
            state["battery_level"]
        )

        # 상태 변화 확인 및 업데이트
        daily_stats_service.start_state(map_name, robot_id, new_state)

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

        # 운영 상태 변화 감지
        self._check_and_update_operation_state(map_name, robot_id, current_node=current_node)

        return True

    def update_battery(self, map_name: str, robot_id: str, battery_level: float, charging_state: int = 0) -> bool:
        """로봇 배터리 정보 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            battery_level: 배터리 잔량 (%)
            charging_state: 충전 상태 (0: 미충전, 1: 충전중)

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)

        redis_service.hset(key, "battery_level", str(battery_level))
        redis_service.hset(key, "charging_state", str(charging_state))
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        # 운영 상태 변화 감지
        self._check_and_update_operation_state(
            map_name, robot_id,
            battery_level=battery_level,
            charging_state=charging_state
        )

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

        # 숫자 필드 변환
        if "current_node" in state:
            state["current_node"] = int(state["current_node"])
        if "final_node" in state:
            state["final_node"] = int(state["final_node"])
        if "battery_level" in state:
            state["battery_level"] = float(state["battery_level"])
        if "charging_state" in state:
            state["charging_state"] = int(state["charging_state"])

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
                    state["battery_level"] = float(state["battery_level"])
                if "charging_state" in state:
                    state["charging_state"] = int(state["charging_state"])

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
