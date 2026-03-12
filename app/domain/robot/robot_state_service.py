"""로봇 상태 관리 서비스 - Redis에 로봇 데이터 저장/조회"""
import json
from typing import Optional, Union
from datetime import datetime

from app.util.redis.client import redis_service
from app.domain.robot.robot_states import RobotOperationState
from app.domain.robot.robot_status import RobotStatus
from app.domain.robot.daily_stats_service import daily_stats_service


class RobotStateService:
    """로봇 상태를 Redis Hash에 저장하는 서비스"""

    def _parse_node_id(self, node_value) -> int:
        """노드 값에서 노드 ID 추출

        Args:
            node_value: int 또는 str("2") 형태

        Returns:
            노드 ID (int)
        """
        if isinstance(node_value, int):
            return node_value
        return int(node_value)


    def _get_robot_key(self, map_name: str, robot_id: str) -> str:
        """로봇 상태 저장 키 생성

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID

        Returns:
            Redis 키 (예: "robot:state:map1:robot1")
        """
        return f"robot:state:{map_name}:{robot_id}"

    def _set_identity_fields(self, key: str, map_name: str, robot_id: str) -> None:
        """mapName, trackNo, robotId 필드 저장"""
        redis_service.hset(key, "map_name", map_name)
        redis_service.hset(key, "track_no", "1")
        redis_service.hset(key, "robot_id", robot_id)

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

    def _update_operation_state(self, map_name: str, robot_id: str) -> None:
        """현재 RobotStatus → RobotOperationState 매핑하여 가동률 통계 업데이트

        RobotStatus가 Redis에 저장된 후 호출하여,
        가동률 계산용 상태로 변환하여 일일 통계에 누적합니다.

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
        """
        state = self.get_robot_state(map_name, robot_id)
        if not state or "status" not in state:
            return

        robot_status = RobotStatus(state["status"])
        battery_state = state.get("battery_state", 0)
        operation_state = RobotOperationState.from_robot_status(robot_status, battery_state)

        # ERROR 상태는 가동률 누적하지 않음
        if operation_state is None:
            return

        # 현재 진행 중인 상태 확인
        current_state_info = daily_stats_service.get_current_state(map_name, robot_id)

        # 상태가 변경되었을 때만 start_state 호출
        if not current_state_info or current_state_info["state"] != operation_state.value:
            daily_stats_service.start_state(map_name, robot_id, operation_state)

    def update_position(
        self,
        map_name: str,
        robot_id: str,
        current_node: int,
        final_node: int = None,
    ) -> bool:
        """로봇 위치 정보 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            current_node: 현재 노드 ID
            final_node: 목적지 노드 ID (Optional)

        Returns:
            성공 여부

        Note:
            - current_node가 1(충전소)이면 charging_state에 따라 CHARGING/WAITING 설정
            - current_node가 1이 아니면 final_node에 따라 RETURN/WORKING 설정
              - final_node가 1이면 RETURN
              - final_node가 1이 아니면 WORKING
            - node_count: 지나간 노드 개수를 누적 추적
        """
        key = self._get_robot_key(map_name, robot_id)

        self._set_identity_fields(key, map_name, robot_id)
        redis_service.hset(key, "current_node", str(current_node))
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        if final_node is not None:
            redis_service.hset(key, "final_node", str(final_node))

        # currentNode 변경에 따른 status 자동 업데이트
        if current_node == 1:
            # 1번 노드(충전소)일 때: 충전 상태를 확인하여 status 결정
            state = self.get_robot_state(map_name, robot_id)
            charging = state.get("charging_state", 0) if state else 0
            if charging == 1:
                redis_service.hset(key, "status", RobotStatus.CHARGING.value)
            else:
                redis_service.hset(key, "status", RobotStatus.WAITING.value)
        elif final_node is not None:
            # final_node가 명시적으로 전달된 경우에만 status 변경
            # final_node=1이면 RETURN(충전소 복귀), 그 외면 WORKING
            if final_node == 1:
                redis_service.hset(key, "status", RobotStatus.RETURN.value)
            else:
                redis_service.hset(key, "status", RobotStatus.WORKING.value)
        # final_node=None이면 status 유지 (arrive/remove 시 현재 상태 보존)

        # RobotStatus → 가동률 상태 매핑 및 통계 업데이트
        self._update_operation_state(map_name, robot_id)

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

        self._set_identity_fields(key, map_name, robot_id)
        redis_service.hset(key, "battery_state", str(battery_state))
        redis_service.hset(key, "charging_state", str(charging_state))
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        # 배터리/충전 상태 변경 시 status도 업데이트 (현재 노드가 1인 경우에만)
        state = self.get_robot_state(map_name, robot_id)
        if state and state.get("current_node") == 1:
            # 1-0 노드에서 배터리/충전 상태 변경 시 status 재계산
            if charging_state == 1:
                redis_service.hset(key, "status", RobotStatus.CHARGING.value)
            else:
                print(f"[RobotStateService] Robot {robot_id} at 1-0: Not charging, setting status to WAITING")
                redis_service.hset(key, "status", RobotStatus.WAITING.value)

        # RobotStatus → 가동률 상태 매핑 및 통계 업데이트
        self._update_operation_state(map_name, robot_id)

        # 상태 변경 사항을 Redis Pub/Sub으로 전송
        self._publish_state_change(map_name, robot_id)

        return True

    def update_status(
        self,
        map_name: str,
        robot_id: str,
        status: Union[RobotStatus, str],
        node: int = None
    ) -> bool:
        """로봇 상태 업데이트

        Args:
            map_name: 맵 이름
            robot_id: 로봇 ID
            status: 상태 (RobotStatus enum 또는 문자열)
            node: 관련 노드 ID (Optional)

        Returns:
            성공 여부
        """
        key = self._get_robot_key(map_name, robot_id)

        self._set_identity_fields(key, map_name, robot_id)
        # RobotStatus enum이면 value 추출
        status_value = status.value if isinstance(status, RobotStatus) else status
        redis_service.hset(key, "status", status_value)
        redis_service.hset(key, "updated_at", datetime.now().isoformat())

        if node is not None:
            redis_service.hset(key, "current_node", str(node))

        # RobotStatus → 가동률 상태 매핑 및 통계 업데이트
        self._update_operation_state(map_name, robot_id)

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
        if "node_count" in state:
            state["node_count"] = int(state["node_count"])

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
                if "node_count" in state:
                    state["node_count"] = int(state["node_count"])

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
