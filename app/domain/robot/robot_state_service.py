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

    def _publish_state_change(self, map_name: str, robot_id: str) -> None:
        """로봇 상태 변경을 Redis Pub/Sub으로 전송

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
        """
        # 현재 상태 조회
        state = self.get_robot_state(map_name, robot_id)
        if not state:
            return

        # Redis 채널로 상태 변경 전송
        channel = f"{map_name}/robot/{robot_id}/state"
        payload = json.dumps(state)
        redis_service.publish(channel, payload)

    def _check_and_update_operation_state(
        self,
        map_name: str,
        robot_id: str,
        current_node: int = None,
        battery_state: float = None,
        charging_state: int = None
    ) -> None:
        """운영 상태 변화 감지 및 일일 통계 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            current_node: 현재 노드 (업데이트된 경우)
            battery_state: 배터리 잔량 (업데이트된 경우)
            charging_state: 충전 상태 (업데이트된 경우)
        """
        # 현재 저장된 상태 조회
        state = self.get_robot_state(map_name, robot_id)
        if not state:
            return

        # 최신 값으로 업데이트
        if current_node is not None:
            state["current_node"] = current_node
        if battery_state is not None:
            state["battery_state"] = battery_state
        if charging_state is not None:
            state["charging_state"] = charging_state

        # 필수 필드 확인
        if "current_node" not in state or "battery_state" not in state or "charging_state" not in state:
            return

        # 현재 운영 상태 결정
        new_state = RobotOperationState.determine_state(
            state["current_node"],
            state["charging_state"],
            state["battery_state"]
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

        # current_node 변경에 따른 status 자동 업데이트
        if current_node == 2:
            # 2번 노드일 때: 배터리와 충전 상태를 확인하여 status 결정
            state = self.get_robot_state(map_name, robot_id)
            if state:
                battery = state.get("battery_state", 100)
                charging = state.get("charging_state", 0)

                # 배터리가 100% 미만이고 충전 중이면 "charging"
                if battery < 100 and charging == 1:
                    redis_service.hset(key, "status", "charging")
                else:
                    # 그 외에는 대기중
                    redis_service.hset(key, "status", "idle")
            else:
                # 상태 정보가 없으면 기본값 idle
                redis_service.hset(key, "status", "idle")
        else:
            # 다른 노드로 이동 → 작업중
            redis_service.hset(key, "status", "working")

        # 운영 상태 변화 감지 (일일 통계용)
        self._check_and_update_operation_state(map_name, robot_id, current_node=current_node)

        # 상태 변경 사항을 Redis Pub/Sub으로 전송
        self._publish_state_change(map_name, robot_id)

        return True

    def update_battery(self, map_name: str, robot_id: str, battery_state: float, charging_state: int = 0) -> bool:
        """로봇 배터리 정보 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            battery_state: 배터리 잔량 (%)
            charging_state: 충전 상태 (0: 미충전, 1: 충전중)

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)

        redis_service.hset(key, "battery_state", str(battery_state))
        redis_service.hset(key, "charging_state", str(charging_state))
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        # 배터리/충전 상태 변경 시 status도 업데이트 (현재 노드가 2번인 경우에만)
        state = self.get_robot_state(map_name, robot_id)
        if state and state.get("current_node") == 2:
            # 2번 노드에서 배터리/충전 상태 변경 시 status 재계산
            if battery_state < 100 and charging_state == 1:
                redis_service.hset(key, "status", "charging")
            else:
                redis_service.hset(key, "status", "idle")

        # 운영 상태 변화 감지
        self._check_and_update_operation_state(
            map_name, robot_id,
            battery_state=battery_state,
            charging_state=charging_state
        )

        # 상태 변경 사항을 Redis Pub/Sub으로 전송
        self._publish_state_change(map_name, robot_id)

        return True

    def update_status(self, map_name: str, robot_id: str, status: str, node: int = None) -> bool:
        """로봇 상태 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            status: 상태 (예: "idle", "moving", "arrived", "charging", "return")
            node: 관련 노드 (Optional)

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)

        redis_service.hset(key, "status", status)
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        if node is not None:
            redis_service.hset(key, "current_node", str(node))

        # 상태 변경 사항을 Redis Pub/Sub으로 전송
        self._publish_state_change(map_name, robot_id)

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
        if "battery_state" in state:
            state["battery_state"] = float(state["battery_state"])
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
                if "battery_state" in state:
                    state["battery_state"] = float(state["battery_state"])
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
